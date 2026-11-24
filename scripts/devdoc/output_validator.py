"""Validate generated documentation structure before human review."""

from dataclasses import dataclass, field
import re

from scripts.devdoc.document_types import validate_document_type
from scripts.devdoc.documentation_reviewer import DocumentationReviewer
from scripts.devdoc.secret_scanner import SecretScanner


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
    UNSAFE_COMMANDS = re.compile(
        r"(?im)(?:^\s*(?:\$\s*)?|\b(?:unauthorized command|run this command)\s*:\s*)"
        r"(?:sudo\s+|powershell(?:\.exe)?\s+|pwsh\s+|cmd(?:\.exe)?\s+/c\s+|"
        r"bash\s+-c\s+|curl\s+[^\n|]*\|\s*(?:sh|bash)|"
        r"rm\s+-rf\s+|aws\s+(?:iam\s+create|s3\s+rm|ec2\s+terminate)|"
        r"(?:chmod\s+777|mkfs(?:\.|\s)|dd\s+if=))",
    )

    def __init__(self, secret_scanner=None):
        self.secret_scanner = secret_scanner or SecretScanner()

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

        try:
            scan = self.secret_scanner.scan(content)
        except Exception:
            return OutputValidationResult(
                False,
                "# Output validation failed\nGenerated content was withheld.",
                ["Generated output could not be security validated."],
            )
        if scan.findings:
            issues.extend(
                f"Generated output contains {finding.lower()}."
                for finding in dict.fromkeys(scan.findings)
            )
        safe_content = scan.redacted_content

        headings = re.findall(r"^#{1,6}\s+(.+?)\s*$", safe_content, re.MULTILINE)
        normalized = {heading.strip().lower() for heading in headings}
        if not headings:
            issues.append("Generated output contains no Markdown headings.")
        for section in self.REQUIRED_SECTIONS[document_type]:
            if section.lower() not in normalized:
                issues.append(f"Missing required section: {section}")
        drift = self.OTHER_TYPE_SECTIONS[document_type].intersection(normalized)
        if drift:
            issues.append("Generated output contains headings associated with another document type: " + ", ".join(sorted(drift)) + ".")

        if self.UNSAFE_COMMANDS.search(safe_content):
            issues.append("Generated output contains a potentially unauthorized command.")

        return OutputValidationResult(
            valid=not issues,
            sanitized_content=safe_content,
            issues=issues,
            secret_findings=list(dict.fromkeys(scan.findings)),
        )
