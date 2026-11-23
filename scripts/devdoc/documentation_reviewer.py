

"""Review documentation drafts before human approval."""

from dataclasses import dataclass, field
import re
from scripts.devdoc.document_types import (
    validate_document_type,
)


@dataclass
class ReviewResult:
    """Structured result of a documentation review."""

    approved: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sections_found: list[str] = field(default_factory=list)


class DocumentationReviewer:
    """Validate documentation structure and flag claims for verification."""

    REQUIRED_SECTIONS = {
        "technical documentation": ["Overview", "Implementation", "Testing"],
        "security documentation": ["Overview", "Security Considerations", "Testing"],
        "architecture documentation": ["Overview", "Architecture", "Components"],
    }

    def review(
        self,
        draft: str,
        document_type: str = "technical documentation",
    ) -> ReviewResult:
        """Review a draft without modifying or publishing it."""

        if not isinstance(draft, str):
            raise ValueError("Draft must be a string.")

        if not draft.strip():
            raise ValueError("Draft cannot be empty.")

        normalized_type = validate_document_type(document_type)
        required_sections = self.REQUIRED_SECTIONS[normalized_type]

        headings = re.findall(r"^#{1,6}\s+(.+?)\s*$", draft, re.MULTILINE)

        normalized_headings = [
            heading.strip().lower()
            for heading in headings
        ]

        sections_found = headings.copy()
        issues = []
        warnings = []

        if not headings:
            issues.append("Documentation contains no Markdown headings.")

        for section in required_sections:
            if section.lower() not in normalized_headings:
                issues.append(f"Missing required section: {section}")

        if len(draft.strip()) < 100:
            warnings.append("Draft is very short; verify that sufficient detail is included.")

        uncertainty_phrases = [
            "TODO",
            "TBD",
            "PLACEHOLDER",
            "UNKNOWN",
            "VERIFY THIS",
        ]

        for phrase in uncertainty_phrases:
            if phrase.lower() in draft.lower():
                warnings.append(
                    f"Draft contains an unresolved marker: {phrase}"
                )

        claim_phrases = [
            "guarantees",
            "completely secure",
            "eliminates all risks",
            "100% secure",
        ]

        for phrase in claim_phrases:
            if phrase.lower() in draft.lower():
                warnings.append(
                    f"Potentially unsupported security claim requires verification: {phrase}"
                )

        return ReviewResult(
            approved=not issues,
            issues=issues,
            warnings=warnings,
            sections_found=sections_found,
        )
