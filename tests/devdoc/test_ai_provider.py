

import pytest

from scripts.devdoc.ai_provider import (
    AIProvider,
    AIProviderError,
    AIRequest,
    AIResponse,
)


def test_valid_ai_request():
    request = AIRequest(
        instruction="Generate security documentation",
        context={"file": "remediation_engine.py"},
    )

    assert request.instruction == "Generate security documentation"
    assert request.context["file"] == "remediation_engine.py"


def test_ai_request_rejects_empty_instruction():
    with pytest.raises(ValueError):
        AIRequest(instruction=" ", context={})


def test_ai_request_rejects_non_string_instruction():
    with pytest.raises(ValueError):
        AIRequest(instruction=123, context={})


def test_ai_request_rejects_non_dictionary_context():
    with pytest.raises(ValueError):
        AIRequest(instruction="Generate documentation", context=[])


def test_valid_ai_response():
    response = AIResponse(
        content="Documentation draft",
        provider="local",
        model="test-model",
        metadata={"tokens": 100},
    )

    assert response.content == "Documentation draft"
    assert response.provider == "local"
    assert response.model == "test-model"
    assert response.metadata["tokens"] == 100


def test_ai_response_rejects_empty_content():
    with pytest.raises(ValueError):
        AIResponse(
            content=" ",
            provider="local",
            model="test-model",
        )


def test_ai_response_rejects_non_string_content():
    with pytest.raises(ValueError):
        AIResponse(
            content=123,
            provider="local",
            model="test-model",
        )


def test_ai_response_rejects_empty_provider():
    with pytest.raises(ValueError):
        AIResponse(
            content="Draft",
            provider=" ",
            model="test-model",
        )


def test_ai_response_rejects_empty_model():
    with pytest.raises(ValueError):
        AIResponse(
            content="Draft",
            provider="local",
            model=" ",
        )


def test_ai_response_rejects_non_dictionary_metadata():
    with pytest.raises(ValueError):
        AIResponse(
            content="Draft",
            provider="local",
            model="test-model",
            metadata=[],
        )


def test_ai_provider_is_abstract():
    with pytest.raises(TypeError):
        AIProvider()


def test_ai_provider_subclass_implements_generate():
    class MockProvider(AIProvider):
        def _generate(self, request):
            return AIResponse(
                content="Generated documentation",
                provider="mock",
                model="test-model",
            )

    provider = MockProvider()
    request = AIRequest(
        instruction="Generate documentation",
        context={},
    )

    response = provider.generate(request)

    assert isinstance(response, AIResponse)
    assert response.content == "Generated documentation"
    assert response.provider == "mock"


def test_ai_provider_error_is_exception():
    error = AIProviderError("Provider connection failed")

    assert isinstance(error, Exception)
    assert str(error) == "Provider connection failed"
