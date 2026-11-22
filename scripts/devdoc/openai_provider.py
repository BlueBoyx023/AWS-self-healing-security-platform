"""OpenAI adapter for DevDoc's vendor-neutral provider interface."""

from __future__ import annotations

import json
import math
import os
from typing import Any

from scripts.devdoc.ai_provider import AIProvider, AIProviderError, AIRequest, AIResponse


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_RETRIES = 2
MAX_ALLOWED_RETRIES = 5
DEFAULT_MAX_CONTEXT_BYTES = 1_000_000
DEFAULT_MAX_RESPONSE_BYTES = 1_000_000

_DRAFT_SCHEMA = {
    "type": "object",
    "properties": {"content": {"type": "string"}},
    "required": ["content"],
    "additionalProperties": False,
}


class OpenAIProvider(AIProvider):
    """Generate a structured Markdown draft through the OpenAI Responses API."""

    def __init__(
        self,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_context_bytes: int = DEFAULT_MAX_CONTEXT_BYTES,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        client: Any = None,
    ):
        super().__init__()

        selected_model = model or os.environ.get("DEVDOC_OPENAI_MODEL", DEFAULT_MODEL)
        if not isinstance(selected_model, str) or not selected_model.strip():
            raise ValueError("OpenAI model must be a non-empty string.")
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("OpenAI timeout must be a positive finite number.")
        if (
            not isinstance(max_retries, int)
            or isinstance(max_retries, bool)
            or not 0 <= max_retries <= MAX_ALLOWED_RETRIES
        ):
            raise ValueError(
                f"OpenAI retries must be an integer from 0 to {MAX_ALLOWED_RETRIES}."
            )
        if (
            not isinstance(max_context_bytes, int)
            or isinstance(max_context_bytes, bool)
            or max_context_bytes <= 0
        ):
            raise ValueError("Maximum context size must be a positive integer.")
        if (
            not isinstance(max_response_bytes, int)
            or isinstance(max_response_bytes, bool)
            or max_response_bytes <= 0
        ):
            raise ValueError("Maximum response size must be a positive integer.")

        self.model = selected_model.strip()
        self.timeout = float(timeout)
        self.max_retries = max_retries
        self.max_context_bytes = max_context_bytes
        self.max_response_bytes = max_response_bytes
        self.client = self._create_client(client)

    def _create_client(self, client: Any) -> Any:
        """Create a configured SDK client, or use an injected test/client seam."""

        if client is not None:
            with_options = getattr(client, "with_options", None)
            if callable(with_options):
                try:
                    return with_options(
                        timeout=self.timeout,
                        max_retries=self.max_retries,
                    )
                except Exception:
                    raise AIProviderError(
                        "OpenAI client options could not be configured."
                    ) from None
            return client

        try:
            from openai import OpenAI
        except ImportError:
            raise AIProviderError(
                "OpenAI support is unavailable. Install scripts/devdoc/requirements-openai.txt."
            ) from None

        try:
            # The SDK reads OPENAI_API_KEY from the environment. Never read,
            # store, print, or include the value in a provider error.
            return OpenAI(
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        except Exception:
            raise AIProviderError(
                "OpenAI client could not be initialized; verify OPENAI_API_KEY configuration."
            ) from None

    def _generate(self, request: AIRequest) -> AIResponse:
        serialized_context = json.dumps(
            request.context,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        context_size = len(request.instruction.encode("utf-8")) + len(
            serialized_context.encode("utf-8")
        )
        if context_size > self.max_context_bytes:
            raise AIProviderError(
                "Request context exceeds the configured size limit."
            )

        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=request.instruction,
                input=serialized_context,
                store=False,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "devdoc_draft",
                        "strict": True,
                        "schema": _DRAFT_SCHEMA,
                    }
                },
            )
        except Exception as error:
            raise AIProviderError(self._safe_error_message(error)) from None

        try:
            content = self._extract_content(response)
        except AIProviderError:
            raise
        except Exception:
            raise AIProviderError("OpenAI returned an invalid response.") from None
        metadata: dict[str, Any] = {}

        request_id = getattr(response, "_request_id", None)
        if (
            isinstance(request_id, str)
            and 0 < len(request_id) <= 128
            and all(char.isprintable() for char in request_id)
            and not self.secret_scanner.scan(request_id).findings
        ):
            metadata["request_id"] = request_id

        usage = getattr(response, "usage", None)
        if usage is not None:
            input_tokens = getattr(usage, "input_tokens", None)
            output_tokens = getattr(usage, "output_tokens", None)
            if isinstance(input_tokens, int) and not isinstance(input_tokens, bool) and input_tokens >= 0:
                metadata["input_tokens"] = input_tokens
            if isinstance(output_tokens, int) and not isinstance(output_tokens, bool) and output_tokens >= 0:
                metadata["output_tokens"] = output_tokens

        return AIResponse(
            content=content,
            provider="openai",
            model=self.model,
            metadata=metadata,
        )

    def _extract_content(self, response: Any) -> str:
        """Validate completed structured output before exposing draft content."""

        if getattr(response, "status", None) != "completed":
            raise AIProviderError("OpenAI returned an incomplete response.")

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise AIProviderError("OpenAI returned an empty response.")
        if len(output_text.encode("utf-8")) > self.max_response_bytes:
            raise AIProviderError("OpenAI response exceeds the configured size limit.")

        try:
            payload = json.loads(output_text)
        except (json.JSONDecodeError, TypeError):
            raise AIProviderError("OpenAI returned malformed structured output.") from None

        if (
            not isinstance(payload, dict)
            or set(payload) != {"content"}
            or not isinstance(payload["content"], str)
            or not payload["content"].strip()
        ):
            raise AIProviderError("OpenAI returned invalid draft content.")

        return payload["content"]

    @staticmethod
    def _safe_error_message(error: Exception) -> str:
        """Map SDK failures to messages that exclude raw provider details."""

        error_name = type(error).__name__
        if error_name == "APITimeoutError":
            return "OpenAI request timed out."
        if error_name == "RateLimitError":
            return "OpenAI rate limit or quota prevented the request."
        if error_name in {"AuthenticationError", "PermissionDeniedError"}:
            return "OpenAI authentication or permission failed."
        if error_name in {"APIConnectionError", "APIStatusError"}:
            return "OpenAI service request failed."
        return "OpenAI provider request failed."
