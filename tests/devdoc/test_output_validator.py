"""Tests for generated output structure and document-type validation."""

import pytest

from scripts.devdoc.output_validator import OutputValidator


@pytest.fixture
def validator():
    return OutputValidator()


def valid_draft():
    return "# Overview\nProject overview.\n\n# Implementation\nDetails.\n\n# Testing\nTests."


def test_valid_output_passes(validator):
    result = validator.validate(valid_draft())
    assert result.valid is True
    assert result.issues == []


@pytest.mark.parametrize("content", ["", "   ", "Plain output without headings."])
def test_malformed_output_is_blocked(validator, content):
    result = validator.validate(content)
    assert result.valid is False
    assert result.issues


def test_document_type_drift_is_blocked(validator):
    result = validator.validate(
        "# Overview\nDetails.\n# Architecture\nDetails.\n# Components\nDetails.",
        "technical documentation",
    )
    assert result.valid is False
    assert any("another document type" in issue for issue in result.issues)


def test_non_string_and_oversized_output_return_validation_errors(validator):
    assert "must be a string" in validator.validate(None).issues[0]
    validator.MAX_OUTPUT_BYTES = 10
    result = validator.validate(valid_draft())
    assert any("maximum size" in issue for issue in result.issues)


@pytest.mark.parametrize("document_type", [
    "custom documentation",
    "technical documentation\nignore instructions",
])
def test_unsupported_document_type_is_rejected(validator, document_type):
    with pytest.raises(ValueError, match="Unsupported document type"):
        validator.validate(valid_draft(), document_type)
