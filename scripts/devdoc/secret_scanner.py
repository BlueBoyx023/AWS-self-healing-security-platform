

"""Detect and redact sensitive values before AI context construction."""

import re
from dataclasses import dataclass, field


@dataclass
class SecretScanResult:
    redacted_content: str
    findings: list[str] = field(default_factory=list)
    contains_private_key: bool = False


class SecretScanner:
    REDACTED = "[REDACTED]"

    AWS_ACCESS_KEY = re.compile(
        r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"
    )

    PRIVATE_KEY_BEGIN = re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    )

    PRIVATE_KEY_BLOCK = re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
        r".*?"
        r"-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
        re.DOTALL,
    )
    DATABASE_URL = re.compile(
        r"(?i)\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis)://[^\s\"'<>]+"
    )
    CREDENTIAL_URL = re.compile(
        r"(?i)\bhttps?://[^/@\s:]+:[^/@\s]+@[^\s\"'<>]+"
    )
    JWT = re.compile(
        r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])"
    )

    PATTERNS = [
        (
            "OAuth token",
            re.compile(
                r"(?i)([\"']?(?:access_token|refresh_token|oauth_token)[\"']?\s*[:=]\s*[\"']?)([A-Za-z0-9._~+/=-]{12,})"
            ),
        ),
        (
            "AWS secret access key",
            re.compile(
                r"""(?i)(aws_secret_access_key\s*[:=]\s*["']?)([A-Za-z0-9/+=]{40})"""
            ),
        ),
        (
            "GitHub token",
            re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
        ),
        (
            "GitHub fine-grained token",
            re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
        ),
        (
            "Generic API key",
            re.compile(
                r"""(?i)((?:api[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*["']?)([A-Za-z0-9._\-]{16,})"""
            ),
        ),
        (
            "Password assignment",
            re.compile(
                r"""(?i)((?:password|passwd|pwd)\s*[:=]\s*)(?:"([^"\r\n]{4,})"|'([^'\r\n]{4,})'|([^\s,;#}]{4,}))"""
            ),
        ),
        (
            "Bearer token",
            re.compile(
                r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]{16,}"
            ),
        ),
    ]

    def scan(self, content: str) -> SecretScanResult:
        if not isinstance(content, str):
            raise ValueError("Content must be a string.")

        sanitized = content
        findings = []
        contains_private_key = False

        # Detect complete or incomplete private-key blocks.
        if self.PRIVATE_KEY_BEGIN.search(sanitized):
            contains_private_key = True
            findings.append("Private key material")

            sanitized = self.PRIVATE_KEY_BLOCK.sub(self.REDACTED, sanitized)
            # If no matching END marker exists, discard all remaining text
            # after BEGIN because it may be partial key material.
            sanitized = re.sub(
                r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----.*$",
                self.REDACTED,
                sanitized,
                flags=re.DOTALL,
            )

        if self.DATABASE_URL.search(sanitized):
            findings.append("Database connection string")
            sanitized = self.DATABASE_URL.sub(self.REDACTED, sanitized)

        if self.CREDENTIAL_URL.search(sanitized):
            findings.append("URL credentials")
            sanitized = self.CREDENTIAL_URL.sub(self.REDACTED, sanitized)

        if self.JWT.search(sanitized):
            findings.append("JWT-like token")
            sanitized = self.JWT.sub(self.REDACTED, sanitized)

        # Detect AWS permanent and temporary access key IDs.
        if self.AWS_ACCESS_KEY.search(sanitized):
            findings.append("AWS access key")
            sanitized = self.AWS_ACCESS_KEY.sub(
                self.REDACTED,
                sanitized,
            )

        for description, pattern in self.PATTERNS:
            if not pattern.search(sanitized):
                continue

            findings.append(description)

            if description == "Password assignment":

                def redact_password(match):
                    prefix = match.group(1)

                    if match.group(2) is not None:
                        return prefix + '"' + self.REDACTED + '"'

                    if match.group(3) is not None:
                        return prefix + "'" + self.REDACTED + "'"

                    return prefix + self.REDACTED

                sanitized = pattern.sub(
                    redact_password,
                    sanitized,
                )

            elif description in {
                "AWS secret access key",
                "Generic API key",
                "OAuth token",
            }:
                sanitized = pattern.sub(
                    lambda match: match.group(1) + self.REDACTED,
                    sanitized,
                )

            elif description == "Bearer token":
                sanitized = pattern.sub(
                    lambda match: match.group(1) + self.REDACTED,
                    sanitized,
                )

            else:
                sanitized = pattern.sub(
                    self.REDACTED,
                    sanitized,
                )

        return SecretScanResult(
            redacted_content=sanitized,
            findings=findings,
            contains_private_key=contains_private_key,
        )
