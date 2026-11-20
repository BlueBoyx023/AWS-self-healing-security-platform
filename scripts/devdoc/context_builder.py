

"""Build bounded, security-filtered context for DevDoc."""

from __future__ import annotations

from pathlib import Path

from scripts.devdoc.secret_scanner import SecretScanner


class ContextBuilder:
    """Collect relevant project files while protecting sensitive data."""

    EXCLUDED_DIRS = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".terraform",
        "secrets",
        ".aws",
        "logs",
    }

    EXCLUDED_FILES = {
        ".env",
        "credentials",
        "credentials.json",
    }

    EXCLUDED_SUFFIXES = {
        ".pem",
        ".key",
        ".p12",
        ".pfx",
        ".tfstate",
        ".tfplan",
        ".pyc",
    }

    TEXT_SUFFIXES = {
        ".py",
        ".md",
        ".rst",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".tf",
        ".sh",
    }

    def __init__(
        self,
        repository: str | Path,
        max_file_bytes: int = 100_000,
        max_total_bytes: int = 1_000_000,
    ):
        self.repository = Path(repository).resolve()

        if not self.repository.exists():
            raise ValueError("Repository path does not exist.")

        if not self.repository.is_dir():
            raise ValueError("Repository path must be a directory.")

        if not (self.repository / ".git").exists():
            raise ValueError("The supplied path is not a Git repository.")

        if (
            not isinstance(max_file_bytes, int)
            or isinstance(max_file_bytes, bool)
            or not isinstance(max_total_bytes, int)
            or isinstance(max_total_bytes, bool)
            or max_file_bytes <= 0
            or max_total_bytes <= 0
        ):
            raise ValueError("File size limits must be positive integers.")

        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes

        # Scan file contents before they enter the AI context.
        self.secret_scanner = SecretScanner()

    def _is_safe_file(self, file_path: Path) -> bool:
        """Check whether a file is safe to collect."""

        try:
            resolved = file_path.resolve(strict=True)
            resolved.relative_to(self.repository)
        except (OSError, ValueError):
            return False

        if not resolved.is_file():
            return False

        relative = resolved.relative_to(self.repository)

        parts = {part.lower() for part in relative.parts}
        filename = resolved.name.lower()

        if parts.intersection(self.EXCLUDED_DIRS):
            return False

        if filename in self.EXCLUDED_FILES:
            return False

        if filename.startswith(".env."):
            return False

        if resolved.suffix.lower() in self.EXCLUDED_SUFFIXES:
            return False

        if resolved.suffix.lower() not in self.TEXT_SUFFIXES:
            return False

        return True

    def _read_file(self, file_path: Path) -> dict:
        """Read, inspect, and sanitize a text file."""

        if not self._is_safe_file(file_path):
            return {
                "status": "skipped",
                "reason": "File is excluded or unsupported.",
            }

        try:
            # Resolve again before reading to reject paths that escape
            # the repository through symbolic links.
            resolved = file_path.resolve(strict=True)
            resolved.relative_to(self.repository)

            size = resolved.stat().st_size

            if size > self.max_file_bytes:
                return {
                    "status": "skipped",
                    "reason": "File exceeds maximum file size.",
                }

            content = resolved.read_text(
                encoding="utf-8",
                errors="replace",
            )

            # Inspect content before it can enter the AI context.
            scan_result = self.secret_scanner.scan(content)

            # Never include files containing private-key material.
            if scan_result.contains_private_key:
                return {
                    "status": "skipped",
                    "reason": "File contains private-key material.",
                }

            sanitized_content = scan_result.redacted_content

            sanitized_size = len(
                sanitized_content.encode("utf-8")
            )

            if sanitized_size > self.max_file_bytes:
                return {
                    "status": "skipped",
                    "reason": "Sanitized file exceeds maximum file size.",
                }

            return {
                "status": "collected",
                "content": sanitized_content,
                "size_bytes": sanitized_size,
                "secret_findings": scan_result.findings,
            }

        except (OSError, ValueError):
            return {
                "status": "skipped",
                "reason": "File could not be safely read.",
            }

    def build(self, classification_report: dict) -> dict:
        """Build a bounded and sanitized project context package."""

        if not isinstance(classification_report, dict):
            raise ValueError(
                "Classification report must be a dictionary."
            )

        classifications = classification_report.get(
            "classifications"
        )

        if not isinstance(classifications, list):
            raise ValueError(
                "Classification report must contain a classifications list."
            )

        collected_files = []
        skipped_files = []
        total_bytes = 0

        for item in classifications:

            if not isinstance(item, dict):
                raise ValueError(
                    "Each classification must be a dictionary."
                )

            relative_path = item.get("path")

            if (
                not isinstance(relative_path, str)
                or not relative_path.strip()
            ):
                raise ValueError(
                    "Each classification must contain a valid path."
                )

            candidate = Path(relative_path)

            if candidate.is_absolute() or ".." in candidate.parts:
                skipped_files.append({
                    "path": relative_path,
                    "reason": "Invalid or unsafe relative path.",
                })
                continue

            file_path = self.repository / candidate

            result = self._read_file(file_path)

            if result["status"] == "skipped":
                skipped_files.append({
                    "path": relative_path,
                    "reason": result["reason"],
                })
                continue

            size = result["size_bytes"]

            if total_bytes + size > self.max_total_bytes:
                skipped_files.append({
                    "path": relative_path,
                    "reason": "Total context size limit reached.",
                })
                continue

            collected_files.append({
                "path": relative_path.replace("\\", "/"),
                "status": item.get("status"),
                "categories": item.get("categories", []),
                "content": result["content"],
                "size_bytes": size,
                "secret_findings": result["secret_findings"],
            })

            total_bytes += size

        return {
            "baseline": classification_report.get("baseline"),
            "files": collected_files,
            "skipped_files": skipped_files,
            "summary": {
                "total_files": len(classifications),
                "collected_files": len(collected_files),
                "skipped_files": len(skipped_files),
                "total_bytes": total_bytes,
            },
        }
