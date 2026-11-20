

"""Provider-independent and security-validated AI interface for DevDoc."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from scripts.devdoc.secret_scanner import SecretScanner


class AIProviderError(Exception):
    """Raised when an AI provider cannot complete a request."""


class AIRequestSecurityError(AIProviderError):
    """Raised when an AI request contains sensitive information."""


@dataclass
class AIRequest:
    """Input supplied to an AI provider."""

    instruction: str
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.instruction, str) or not self.instruction.strip():
            raise ValueError("Instruction must be a non-empty string.")

        if not isinstance(self.context, dict):
            raise ValueError("Context must be a dictionary.")


@dataclass
class AIResponse:
    """Standardized response returned by an AI provider."""

    content: str
    provider: str
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.content, str):
            raise ValueError("Response content must be a string.")

        if not self.content.strip():
            raise ValueError("Response content cannot be empty.")

        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("Provider name must be a non-empty string.")

        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("Model name must be a non-empty string.")

        if not isinstance(self.metadata, dict):
            raise ValueError("Response metadata must be a dictionary.")


class AIProvider(ABC):
    """Abstract interface with a mandatory outbound security gate."""

    def __init__(self):
        self.secret_scanner = SecretScanner()

    def validate_request(self, request: AIRequest) -> None:
        """Reject requests containing detected sensitive material."""

        if not isinstance(request, AIRequest):
            raise AIRequestSecurityError(
                "Provider received an invalid AI request."
            )

        # Inspect the complete serialized request, including nested context.
        import json

        serialized_request = json.dumps(
            {
                "instruction": request.instruction,
                "context": request.context,
            },
            ensure_ascii=True,
            default=str,
        )

        scan_result = self.secret_scanner.scan(serialized_request)

        if scan_result.contains_private_key:
            raise AIRequestSecurityError(
                "Request rejected: private-key material detected."
            )

        if scan_result.findings:
            raise AIRequestSecurityError(
                "Request rejected: sensitive information detected."
            )

    def generate(self, request: AIRequest) -> AIResponse:
        """Validate the request before provider-specific generation."""

        self.validate_request(request)
        return self._generate(request)

    @abstractmethod
    def _generate(self, request: AIRequest) -> AIResponse:
        """Implement provider-specific generation in subclasses."""
        raise NotImplementedError
