"""Validate generated documentation structure before human review."""

from dataclasses import dataclass, field
import re

from scripts.devdoc.document_types import validate_document_type
from scripts.devdoc.documentation_reviewer import DocumentationReviewer


@dataclass
class OutputValidationResult:
    """Validation result for an untrusted generated draft."""

    valid: bool
    sanitized_content: str
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    secret_findings: list[str] = field(default_factory=list)


class OutputValidator:
    """Check generated output structure and requested document type."""

    MAX_OUTPUT_BYTES = 1_000_000
    REQUIRED_SECTIONS = DocumentationReviewer.REQUIRED_SECTIONS
    OTHER_TYPE_SECTIONS = {
        "security documentation": {"architecture", "components", "implementation"},
        "architecture documentation": {"security considerations", "implementation"},
        "technical documentation": {"security considerations", "architecture", "components"},
    }

    def validate(self, content, document_type="technical documentation"):
        """Validate output without executing or modifying generated content."""
        document_type = validate_document_type(document_type)
        if not isinstance(content, str):
            return OutputValidationResult(False, "", ["Generated output must be a string."])
        if not content.strip():
            return OutputValidationResult(False, content, ["Generated output is empty."])

        issues = []
        try:
            output_size = len(content.encode("utf-8"))
        except UnicodeEncodeError:
            return OutputValidationResult(
                False,
                "# Output validation failed\nGenerated content was withheld.",
                ["Generated output contains invalid text encoding."],
            )
        if output_size > self.MAX_OUTPUT_BYTES:
            issues.append("Generated output exceeds the maximum size.")

        headings = re.findall(r"^#{1,6}\s+(.+?)\s*$", content, re.MULTILINE)
        normalized = {heading.strip().lower() for heading in headings}
        if not headings:
            issues.append("Generated output contains no Markdown headings.")
        for section in self.REQUIRED_SECTIONS[document_type]:
            if section.lower() not in normalized:
                issues.append(f"Missing required section: {section}")
        drift = self.OTHER_TYPE_SECTIONS[document_type].intersection(normalized)
        if drift:
            issues.append("Generated output contains headings associated with another document type: " + ", ".join(sorted(drift)) + ".")

        return OutputValidationResult(
            valid=not issues,
            sanitized_content=content,
            issues=issues,
        )
