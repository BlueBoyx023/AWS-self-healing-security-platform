

import pytest

from scripts.devdoc.ai_provider import (
    AIProvider,
    AIProviderError,
    AIRequest,
    AIRequestSecurityError,
    AIResponse,
)


# ============================================================
# AI REQUEST VALIDATION
# ============================================================

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


# ============================================================
# AI RESPONSE VALIDATION
# ============================================================

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


# ============================================================
# MOCK PROVIDER
# ============================================================

class TrackingProvider(AIProvider):
    """Mock provider that tracks execution attempts."""

    def __init__(self):
        super().__init__()
        self.called = False

    def _generate(self, request):
        self.called = True

        return AIResponse(
            content="Generated documentation",
            provider="mock",
            model="test-model",
        )


# ============================================================
# AI PROVIDER INTERFACE
# ============================================================

def test_ai_provider_is_abstract():
    with pytest.raises(TypeError):
        AIProvider()


def test_ai_provider_subclass_implements_generate():
    provider = TrackingProvider()

    request = AIRequest(
        instruction="Generate documentation",
        context={},
    )

    response = provider.generate(request)

    assert isinstance(response, AIResponse)
    assert response.content == "Generated documentation"
    assert response.provider == "mock"
    assert provider.called is True


def test_ai_provider_error_is_exception():
    error = AIProviderError("Provider connection failed")

    assert isinstance(error, Exception)
    assert str(error) == "Provider connection failed"


# ============================================================
# OUTBOUND AI SECURITY VALIDATION
# ============================================================

def test_ai_provider_rejects_nested_aws_secret():
    provider = TrackingProvider()

    request = AIRequest(
        instruction="Generate documentation",
        context={
            "project": {
                "configuration": {
                    "aws_access_key": "AKIAIOSFODNN7EXAMPLE"
                }
            }
        },
    )

    with pytest.raises(AIRequestSecurityError):
        provider.generate(request)

    assert provider.called is False


def test_ai_provider_rejects_nested_github_token():
    provider = TrackingProvider()

    request = AIRequest(
        instruction="Generate documentation",
        context={
            "files": [
                {
                    "path": "README.md",
                    "content": "Token: ghp_" + ("A" * 36),
                }
            ]
        },
    )

    with pytest.raises(AIRequestSecurityError):
        provider.generate(request)

    assert provider.called is False


def test_ai_provider_rejects_private_key_material():
    provider = TrackingProvider()

    request = AIRequest(
        instruction="Generate documentation",
        context={
            "configuration": """
-----BEGIN RSA PRIVATE KEY-----
example-private-key-material
-----END RSA PRIVATE KEY-----
"""
        },
    )

    with pytest.raises(AIRequestSecurityError):
        provider.generate(request)

    assert provider.called is False


def test_ai_provider_rejects_secret_in_instruction():
    provider = TrackingProvider()

    request = AIRequest(
        instruction="Document this key: AKIAIOSFODNN7EXAMPLE",
        context={},
    )

    with pytest.raises(AIRequestSecurityError):
        provider.generate(request)

    assert provider.called is False


def test_ai_provider_rejects_invalid_request():
    provider = TrackingProvider()

    with pytest.raises(AIRequestSecurityError):
        provider.generate("invalid request")

    assert provider.called is False


def test_ai_provider_allows_clean_nested_context():
    provider = TrackingProvider()

    request = AIRequest(
        instruction="Generate security documentation",
        context={
            "project": {
                "name": "AWS Self-Healing Security Platform",
                "files": [
                    "orchestrator.py",
                    "verification_engine.py",
                ],
            }
        },
    )

    response = provider.generate(request)

    assert isinstance(response, AIResponse)
    assert provider.called is True


def test_ai_provider_rejects_secret_without_exposing_it_in_error():
    provider = TrackingProvider()

    secret = "AKIAIOSFODNN7EXAMPLE"

    request = AIRequest(
        instruction="Generate documentation",
        context={"credentials": secret},
    )

    with pytest.raises(AIRequestSecurityError) as exc_info:
        provider.generate(request)

    assert secret not in str(exc_info.value)
    assert provider.called is False


def test_ai_provider_rejects_nested_database_secret_before_outbound_call():
    provider = TrackingProvider()
    request = AIRequest("Generate docs", {"items": [{
        "url": "postgresql://dev:synthetic-db-password@db.example.test/app"
    }]})
    with pytest.raises(AIRequestSecurityError):
        provider.generate(request)
    assert provider.called is False


def test_ai_provider_rejects_nested_jwt_before_outbound_call():
    provider = TrackingProvider()
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzeW50aGV0aWMifQ.synthetic-signature"
    with pytest.raises(AIRequestSecurityError):
        provider.generate(AIRequest("Generate docs", {"items": [token]}))
    assert provider.called is False


def test_ai_provider_rejects_oauth_refresh_token_before_outbound_call():
    provider = TrackingProvider()
    with pytest.raises(AIRequestSecurityError):
        provider.generate(AIRequest("Generate docs", {"tokens": {
            "refresh_token": "synthetic-oauth-token-1234567890"
        }}))
    assert provider.called is False


def test_ai_provider_rejects_custom_object_without_stringifying_it():
    provider = TrackingProvider()

    class Dangerous:
        def __str__(self):
            raise AssertionError("__str__ must not run")

    with pytest.raises(AIRequestSecurityError):
        provider.generate(AIRequest("Generate docs", {"value": Dangerous()}))
    assert provider.called is False
