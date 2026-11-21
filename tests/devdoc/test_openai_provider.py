import json
import sys
from types import SimpleNamespace

import pytest

from scripts.devdoc.ai_provider import AIProviderError, AIRequest, AIRequestSecurityError
from scripts.devdoc.openai_provider import OpenAIProvider


class FakeResponses:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response=None, error=None):
        self.responses = FakeResponses(response, error)
        self.options = None

    def with_options(self, **kwargs):
        self.options = kwargs
        return self


def make_response(content, **attributes):
    return SimpleNamespace(
        status="completed",
        output_text=json.dumps({"content": content}),
        **attributes,
    )


def test_openai_provider_maps_request_and_structured_response():
    response = make_response(
        "# Overview\nDraft",
        _request_id="req_test_123",
        usage=SimpleNamespace(input_tokens=42, output_tokens=18),
    )
    client = FakeClient(response)
    provider = OpenAIProvider(
        model="configured-model",
        timeout=12,
        max_retries=1,
        client=client,
    )

    result = provider.generate(
        AIRequest("Write a draft", {"files": [{"path": "README.md"}]})
    )

    call = client.responses.calls[0]
    assert call["model"] == "configured-model"
    assert call["instructions"] == "Write a draft"
    assert json.loads(call["input"]) == {"files": [{"path": "README.md"}]}
    assert call["store"] is False
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True
    assert client.options == {"timeout": 12.0, "max_retries": 1}
    assert result.content == "# Overview\nDraft"
    assert result.provider == "openai"
    assert result.model == "configured-model"
    assert result.metadata == {
        "request_id": "req_test_123",
        "input_tokens": 42,
        "output_tokens": 18,
    }


def test_secret_request_is_rejected_before_sdk_invocation():
    client = FakeClient(make_response("Draft"))
    provider = OpenAIProvider(client=client)
    synthetic_secret = "AKIAIOSFODNN7EXAMPLE"

    with pytest.raises(AIRequestSecurityError) as exc_info:
        provider.generate(
            AIRequest("Generate docs", {"content": synthetic_secret})
        )

    assert synthetic_secret not in str(exc_info.value)
    assert client.responses.calls == []


@pytest.mark.parametrize(
    "output_text",
    [
        "",
        "not-json",
        "{}",
        '{"content": "   "}',
        '{"content": "draft", "extra": true}',
        '[{"content": "draft"}]',
    ],
)
def test_rejects_malformed_or_invalid_structured_response(output_text):
    provider = OpenAIProvider(
        client=FakeClient(SimpleNamespace(status="completed", output_text=output_text))
    )

    with pytest.raises(AIProviderError):
        provider.generate(AIRequest("Generate docs", {"files": []}))


def test_rejects_incomplete_response():
    provider = OpenAIProvider(
        client=FakeClient(
            SimpleNamespace(status="incomplete", output_text='{"content":"draft"}')
        )
    )

    with pytest.raises(AIProviderError, match="incomplete"):
        provider.generate(AIRequest("Generate docs", {"files": []}))


def test_context_limit_is_checked_before_sdk_invocation():
    client = FakeClient(make_response("Draft"))
    provider = OpenAIProvider(client=client, max_context_bytes=8)

    with pytest.raises(AIProviderError, match="size limit"):
        provider.generate(AIRequest("Generate docs", {"files": ["too large"]}))

    assert client.responses.calls == []


@pytest.mark.parametrize(
    ("error_name", "expected_message"),
    [
        ("APITimeoutError", "OpenAI request timed out."),
        ("RateLimitError", "OpenAI rate limit or quota prevented the request."),
        ("AuthenticationError", "OpenAI authentication or permission failed."),
        ("APIConnectionError", "OpenAI service request failed."),
        ("UnexpectedSDKError", "OpenAI provider request failed."),
    ],
)
def test_sanitizes_sdk_failures(error_name, expected_message):
    secret_like_detail = "synthetic-sensitive-detail-never-return"
    error_type = type(error_name, (Exception,), {})
    provider = OpenAIProvider(
        client=FakeClient(error=error_type(secret_like_detail))
    )

    with pytest.raises(AIProviderError) as exc_info:
        provider.generate(AIRequest("Generate docs", {"files": []}))

    assert str(exc_info.value) == expected_message
    assert secret_like_detail not in str(exc_info.value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model": " "},
        {"timeout": 0},
        {"timeout": float("inf")},
        {"max_retries": -1},
        {"max_retries": 6},
        {"max_retries": True},
        {"max_context_bytes": 0},
        {"max_context_bytes": True},
    ],
)
def test_rejects_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        OpenAIProvider(client=FakeClient(), **kwargs)


def test_sdk_client_is_configured_without_reading_api_key(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.responses = FakeResponses(make_response("Draft"))

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    provider = OpenAIProvider(model="sdk-model", timeout=9, max_retries=0)

    assert captured == {"timeout": 9.0, "max_retries": 0}
    assert provider.model == "sdk-model"


def test_model_can_be_configured_through_environment(monkeypatch):
    monkeypatch.setenv("DEVDOC_OPENAI_MODEL", "environment-model")

    provider = OpenAIProvider(client=FakeClient())

    assert provider.model == "environment-model"


def test_missing_sdk_error_does_not_include_configuration_values(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)

    with pytest.raises(AIProviderError, match="OpenAI support is unavailable"):
        OpenAIProvider()
