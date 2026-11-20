

import pytest

from scripts.devdoc.ai_provider import (
    AIProvider,
    AIProviderError,
    AIRequest,
    AIResponse,
)
from scripts.devdoc.draft_generator import DraftGenerator


class MockProvider(AIProvider):
    def __init__(self):
        super().__init__()
        self.last_request = None

    def _generate(self, request):
        self.last_request = request

        return AIResponse(
            content="# Security Documentation\n\nDraft content.",
            provider="mock",
            model="test-model",
        )


def test_generate_documentation_draft():
    provider = MockProvider()
    generator = DraftGenerator(provider)

    context = {
        "files": [
            {
                "path": "lambda/remediation_engine.py",
                "content": "def remediate(): pass",
            }
        ]
    }

    response = generator.generate_draft(context)

    assert isinstance(response, AIResponse)
    assert response.provider == "mock"
    assert "# Security Documentation" in response.content


def test_generator_passes_context_to_provider():
    provider = MockProvider()
    generator = DraftGenerator(provider)

    context = {"files": [{"path": "example.py", "content": "print('test')"}]}

    generator.generate_draft(context)

    assert provider.last_request.context == context


def test_generator_creates_ai_request():
    provider = MockProvider()
    generator = DraftGenerator(provider)

    generator.generate_draft({"files": []})

    assert isinstance(provider.last_request, AIRequest)


def test_generator_uses_default_document_type():
    provider = MockProvider()
    generator = DraftGenerator(provider)

    generator.generate_draft({"files": []})

    assert "technical documentation" in provider.last_request.instruction


def test_generator_accepts_custom_document_type():
    provider = MockProvider()
    generator = DraftGenerator(provider)

    generator.generate_draft(
        {"files": []},
        document_type="security design documentation",
    )

    assert "security design documentation" in provider.last_request.instruction


def test_generator_rejects_non_dictionary_context():
    generator = DraftGenerator(MockProvider())

    with pytest.raises(ValueError):
        generator.generate_draft([])


def test_generator_rejects_empty_context():
    generator = DraftGenerator(MockProvider())

    with pytest.raises(ValueError):
        generator.generate_draft({})


def test_generator_rejects_empty_document_type():
    generator = DraftGenerator(MockProvider())

    with pytest.raises(ValueError):
        generator.generate_draft(
            {"files": []},
            document_type=" ",
        )


def test_generator_rejects_invalid_provider():
    with pytest.raises(TypeError):
        DraftGenerator("not a provider")


def test_generator_rejects_invalid_provider_response():
    class InvalidProvider(AIProvider):
        def _generate(self, request):
            return "not an AIResponse"

    generator = DraftGenerator(InvalidProvider())

    with pytest.raises(TypeError):
        generator.generate_draft({"files": []})


def test_generator_propagates_provider_errors():
    class FailingProvider(AIProvider):
        def _generate(self, request):
            raise AIProviderError("Provider unavailable")

    generator = DraftGenerator(FailingProvider())

    with pytest.raises(AIProviderError):
        generator.generate_draft({"files": []})


def test_generator_does_not_write_files():
    provider = MockProvider()
    generator = DraftGenerator(provider)

    response = generator.generate_draft({"files": []})

    assert isinstance(response, AIResponse)
    assert not hasattr(generator, "save_draft")
    assert not hasattr(generator, "write_file")
