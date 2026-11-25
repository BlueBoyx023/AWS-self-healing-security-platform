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
    UNSAFE_COMMAND_BODY = (
        r"(?:sudo\s+|powershell(?:\.exe)?\s+|pwsh\s+|cmd(?:\.exe)?\s+/c\s+|"
        r"bash\s+-c\s+|curl\s+[^\n|]*\|\s*(?:sh|bash)|"
        r"rm\s+-rf\s+|aws\s+(?:iam\s+create|s3\s+rm|ec2\s+terminate)|"
        r"(?:chmod\s+777|mkfs(?:\.|\s)|dd\s+if=))"
    )
    UNSAFE_COMMAND_LINE = re.compile(
        r"^\s*(?:\$\s*)?" + UNSAFE_COMMAND_BODY,
        re.IGNORECASE,
    )
    UNSAFE_COMMAND_LABEL = re.compile(
        r"\b(?:unauthorized command|run this command)\s*:\s*`?"
        + UNSAFE_COMMAND_BODY,
        re.IGNORECASE,
    )
    UNSAFE_COMMAND_PROSE = re.compile(
        r"\b(?:run|execute)\s+(?:(?:the|this|following)\s+)?"
        r"(?:command\s*:?\s*)?`?" + UNSAFE_COMMAND_BODY,
        re.IGNORECASE,
    )
    UNSAFE_COMMAND_INSTRUCTION = re.compile(
        r"\b(?:run|execute)\b"
        r"(?:(?!\b(?:run|execute)\b)[^:!?;.\n]){0,120}:\s*`?"
        + UNSAFE_COMMAND_BODY,
        re.IGNORECASE,
    )
    NEGATED_EXECUTION = re.compile(
        r"(?:\bdo\s+not|\bdon't|\bdont|\bnever|"
        r"\b(?:must|should|will)\s+not|\b(?:mustn't|shouldn't|won't)|"
        r"\bcannot|\bcan't|\bavoid)\s+(?:ever\s+)?$",
        re.IGNORECASE,
    )
    FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
    FENCE_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
    MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
    MARKDOWN_PREFIX = re.compile(r"^\s*(?:>\s*|(?:[-+*]|\d+[.)])\s+)")
    HTML_BLOCK_OPEN = re.compile(
        r"^ {0,3}</?\s*([A-Za-z][A-Za-z0-9:-]*)\b",
        re.IGNORECASE,
    )
    HTML_AUTOLINK = re.compile(
        r"^ {0,3}<(?:[A-Za-z][A-Za-z0-9.+-]{1,31}:[^<>\s]+|"
        r"[^<>\s@]+@[^<>\s@]+)>"
    )
    HTML_CDATA_OPEN = re.compile(r"^ {0,3}<!\[CDATA\[")
    HTML_PI_OPEN = re.compile(r"^ {0,3}<\?")
    HTML_DECL_OPEN = re.compile(r"^ {0,3}<![A-Z]")
    HTML_TAG = re.compile(
        r"<\s*(/?)\s*([A-Za-z][A-Za-z0-9:-]*)\b"
        r"(?:[^'\">]|\"[^\"]*\"|'[^']*')*>",
        re.IGNORECASE,
    )
    HTML_VOID_TAGS = frozenset({
        "area", "base", "basefont", "br", "bgsound", "col", "command",
        "embed", "frame", "hr", "img", "input", "keygen", "link", "meta",
        "param", "source", "track", "wbr",
    })
    HTML_RAW_TEXT_TAGS = frozenset({"pre", "script", "style", "textarea"})
    HTML_BLOCK_ERROR = "Generated output contains a malformed or unclosed HTML block."

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

        headings, malformed_fence, unclosed_comment, malformed_html = (
            self._headings_outside_fences(safe_content)
        )
        normalized = {heading.strip().lower() for heading in headings}
        if malformed_fence:
            issues.append("Generated output contains a malformed or unclosed fenced code block.")
        if unclosed_comment:
            issues.append("Generated output contains an unclosed HTML comment.")
        if malformed_html:
            issues.append(self.HTML_BLOCK_ERROR)
        if not headings:
            issues.append("Generated output contains no Markdown headings.")
        for section in self.REQUIRED_SECTIONS[document_type]:
            if section.lower() not in normalized:
                issues.append(f"Missing required section: {section}")
        drift = self.OTHER_TYPE_SECTIONS[document_type].intersection(normalized)
        if drift:
            issues.append("Generated output contains headings associated with another document type: " + ", ".join(sorted(drift)) + ".")

        if self._contains_unsafe_command(safe_content):
            issues.append("Generated output contains a potentially unauthorized command.")

        return OutputValidationResult(
            valid=not issues,
            sanitized_content=safe_content,
            issues=issues,
            secret_findings=list(dict.fromkeys(scan.findings)),
        )

    @classmethod
    def _headings_outside_fences(cls, content):
        """Return visible Markdown headings and malformed markup state."""

        headings = []
        active_fence = None
        malformed_fence = False
        in_html_comment = False
        raw_html_stack = []
        html_block_active = False
        html_raw_text_block = False
        html_raw_mode = None
        malformed_html = False

        for line in content.splitlines():
            if active_fence is not None:
                closing = cls.FENCE_CLOSE.match(line)
                if (
                    closing
                    and closing.group(1)[0] == active_fence[0]
                    and len(closing.group(1)) >= len(active_fence)
                ):
                    active_fence = None
                continue

            if html_raw_mode is not None:
                terminator = {"cdata": "]]>", "processing": "?>", "declaration": ">"}[
                    html_raw_mode
                ]
                if terminator in line:
                    html_raw_mode = None
                continue

            if html_block_active:
                visible_line, in_html_comment = cls._mask_html_comments(
                    line,
                    in_html_comment,
                )

                if html_raw_text_block:
                    if raw_html_stack:
                        raw_html_stack, malformed_html = cls._advance_html_block(
                            visible_line,
                            raw_html_stack,
                            malformed_html,
                        )
                    if not raw_html_stack:
                        html_block_active = False
                        html_raw_text_block = False
                    continue

                if not line.strip():
                    if raw_html_stack:
                        malformed_html = True
                    raw_html_stack = []
                    html_block_active = False
                    continue

                if raw_html_stack:
                    raw_html_stack, malformed_html = cls._advance_html_block(
                        visible_line,
                        raw_html_stack,
                        malformed_html,
                    )
                if html_raw_text_block and not raw_html_stack:
                    html_block_active = False
                    html_raw_text_block = False
                continue

            opening = (
                None
                if in_html_comment or html_block_active or html_raw_mode
                else cls.FENCE_OPEN.match(line)
            )
            if opening:
                marker, info = opening.groups()
                # CommonMark forbids backticks in a backtick fence's info string.
                if marker[0] == "`" and "`" in info:
                    malformed_fence = True
                    active_fence = marker
                    continue
                active_fence = marker
                continue

            visible_line, in_html_comment = cls._mask_html_comments(
                line,
                in_html_comment,
            )

            if cls.HTML_AUTOLINK.match(visible_line):
                continue

            raw_openers = (
                (cls.HTML_CDATA_OPEN, "cdata", "]]>"),
                (cls.HTML_PI_OPEN, "processing", "?>"),
                (cls.HTML_DECL_OPEN, "declaration", ">"),
            )
            raw_open = next(
                (
                    (mode, terminator)
                    for pattern, mode, terminator in raw_openers
                    if pattern.match(visible_line)
                ),
                None,
            )
            if raw_open:
                mode, terminator = raw_open
                if terminator not in visible_line:
                    html_raw_mode = mode
                continue

            block_open = cls.HTML_BLOCK_OPEN.match(visible_line)
            if block_open:
                tag = block_open.group(1).lower()
                html_block_active = True
                html_raw_text_block = tag in cls.HTML_RAW_TEXT_TAGS
                raw_html_stack = []
                tokens = list(cls.HTML_TAG.finditer(visible_line))
                if not tokens or tokens[0].group(2).lower() != tag:
                    malformed_html = True
                    if tag not in cls.HTML_VOID_TAGS:
                        raw_html_stack = [tag]
                elif tokens[0].group(1):
                    # CommonMark type 6 also treats a standalone closing tag as
                    # an HTML block. It has no local opening stack to balance.
                    pass
                elif tag not in cls.HTML_VOID_TAGS:
                    raw_html_stack, malformed_html = cls._advance_html_block(
                        visible_line,
                        raw_html_stack,
                        malformed_html,
                    )
                if html_raw_text_block and not raw_html_stack:
                    close_pattern = re.compile(
                        r"</\s*" + re.escape(tag) + r"\s*>",
                        re.IGNORECASE,
                    )
                    if close_pattern.search(visible_line):
                        html_block_active = False
                        html_raw_text_block = False
                    else:
                        # A self-closing raw-text tag does not end a CommonMark type 1 block.
                        malformed_html = True
                        raw_html_stack = [tag]
                continue

            heading = cls.MARKDOWN_HEADING.match(visible_line)
            if heading:
                headings.append(heading.group(1))

        return (
            headings,
            malformed_fence or active_fence is not None,
            in_html_comment,
            malformed_html or bool(raw_html_stack) or html_raw_mode is not None,
        )

    @classmethod
    def _advance_html_block(cls, line, stack, malformed):
        """Track nested block tags and fail closed on malformed nesting."""

        tokens = list(cls.HTML_TAG.finditer(line))
        index = 0
        while index < len(tokens):
            if stack and stack[-1] in cls.HTML_RAW_TEXT_TAGS:
                closing_index = next(
                    (
                        candidate
                        for candidate in range(index, len(tokens))
                        if tokens[candidate].group(1)
                        and tokens[candidate].group(2).lower() == stack[-1]
                    ),
                    None,
                )
                if closing_index is None:
                    break
                stack.pop()
                index = closing_index + 1
                continue

            token = tokens[index]
            closing, name = token.groups()
            name = name.lower()
            if name in cls.HTML_VOID_TAGS:
                index += 1
                continue

            token_text = token.group(0)
            if closing:
                if stack and stack[-1] == name:
                    stack.pop()
                else:
                    malformed = True
            elif not token_text.rstrip().endswith("/>"):
                stack.append(name)
            index += 1

        return stack, malformed

    @staticmethod
    def _mask_html_comments(line, in_comment):
        """Blank HTML comment text while preserving positions and line shape."""

        visible = []
        position = 0

        while position < len(line):
            if in_comment:
                close = line.find("-->", position)
                if close == -1:
                    visible.append(" " * (len(line) - position))
                    position = len(line)
                else:
                    end = close + len("-->")
                    visible.append(" " * (end - position))
                    position = end
                    in_comment = False
                continue

            opening = line.find("<!--", position)
            if opening == -1:
                visible.append(line[position:])
                position = len(line)
            else:
                visible.append(line[position:opening])
                visible.append(" " * len("<!--"))
                position = opening + len("<!--")
                in_comment = True

        return "".join(visible), in_comment

    @classmethod
    def _contains_unsafe_command(cls, content):
        """Detect selected dangerous commands after common Markdown prefixes."""

        normalized_content = re.sub(
            r"\\\r?\n[ \t]*(?:(?:>[ \t]*)|(?:[-+*]|\d+[.)])[ \t]+)*",
            " ",
            content,
        )

        for line in normalized_content.splitlines():
            normalized = line
            # Repeatedly peel blockquote/list markers, supporting nested and
            # combined forms such as ``> - 1. sudo ...``.
            while True:
                prefix = cls.MARKDOWN_PREFIX.match(normalized)
                if not prefix:
                    break
                normalized = normalized[prefix.end():]

            if cls.UNSAFE_COMMAND_LINE.search(normalized):
                return True

            for pattern in (
                cls.UNSAFE_COMMAND_LABEL,
                cls.UNSAFE_COMMAND_PROSE,
                cls.UNSAFE_COMMAND_INSTRUCTION,
            ):
                for match in pattern.finditer(normalized):
                    if cls.NEGATED_EXECUTION.search(normalized[:match.start()]):
                        continue
                    return True

        return False
