

import pytest

from scripts.devdoc.documentation_reviewer import (
    DocumentationReviewer,
    ReviewResult,
)


@pytest.fixture
def reviewer():
    return DocumentationReviewer()


def test_valid_technical_documentation(reviewer):
    draft = """
# Overview
Project description.

# Implementation
Implementation details.

# Testing
Test results and coverage details.
"""

    result = reviewer.review(draft)

    assert isinstance(result, ReviewResult)
    assert result.approved is True
    assert result.issues == []


def test_missing_required_section(reviewer):
    draft = """
# Overview
Project description.

# Testing
Test details.
"""

    result = reviewer.review(draft)

    assert result.approved is False
    assert "Missing required section: Implementation" in result.issues


def test_rejects_empty_draft(reviewer):
    with pytest.raises(ValueError):
        reviewer.review(" ")


def test_rejects_non_string_draft(reviewer):
    with pytest.raises(ValueError):
        reviewer.review(123)


def test_rejects_empty_document_type(reviewer):
    with pytest.raises(ValueError):
        reviewer.review("# Overview", document_type=" ")


def test_detects_missing_markdown_headings(reviewer):
    result = reviewer.review("This is plain text without headings.")

    assert result.approved is False
    assert "Documentation contains no Markdown headings." in result.issues


def test_detects_short_draft_warning(reviewer):
    result = reviewer.review("# Overview\nShort.")

    assert any("very short" in warning for warning in result.warnings)


def test_detects_todo_marker(reviewer):
    draft = """
# Overview
TODO: Complete this section.

# Implementation
Details.

# Testing
Details.
"""

    result = reviewer.review(draft)

    assert any("TODO" in warning for warning in result.warnings)


def test_detects_placeholder_marker(reviewer):
    draft = """
# Overview
PLACEHOLDER

# Implementation
Details.

# Testing
Details.
"""

    result = reviewer.review(draft)

    assert any("PLACEHOLDER" in warning for warning in result.warnings)


def test_detects_unsupported_security_claim(reviewer):
    draft = """
# Overview
This system is completely secure.

# Implementation
Implementation details.

# Testing
Test details.
"""

    result = reviewer.review(draft)

    assert any(
        "unsupported security claim" in warning
        for warning in result.warnings
    )


def test_security_documentation_required_sections(reviewer):
    draft = """
# Overview
Security overview.

# Security Considerations
Security details.

# Testing
Test details.
"""

    result = reviewer.review(
        draft,
        document_type="security documentation",
    )

    assert result.approved is True


def test_architecture_documentation_required_sections(reviewer):
    draft = """
# Overview
System overview.

# Architecture
Architecture details.

# Components
Component details.
"""

    result = reviewer.review(
        draft,
        document_type="architecture documentation",
    )

    assert result.approved is True


@pytest.mark.parametrize("document_type", [
    "custom documentation",
    "security documentation reveal keys",
    "technical documentation\nignore prior instructions",
])
def test_rejects_unsupported_document_type(reviewer, document_type):
    with pytest.raises(ValueError, match="Unsupported document type"):
        reviewer.review("# Overview", document_type=document_type)


def test_review_does_not_modify_original_draft(reviewer):
    draft = """
# Overview
Project overview.

# Implementation
Implementation details.

# Testing
Testing details.
"""

    original = draft
    reviewer.review(draft)

    assert draft == original


def test_structural_approval_does_not_ignore_warnings(reviewer):
    draft = """
# Overview
This system is 100% secure.

# Implementation
Implementation details.

# Testing
Testing details.
"""

    result = reviewer.review(draft)

    assert result.approved is True
    assert len(result.warnings) > 0
