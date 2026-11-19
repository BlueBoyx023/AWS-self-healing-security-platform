

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


class GitChangeAnalyzer:
    """Analyze repository changes while excluding sensitive and generated files."""

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

    def __init__(self, repository: str | Path):
        self.repository = Path(repository).resolve()

        if not self.repository.exists():
            raise ValueError("Repository path does not exist.")

        if not self.repository.is_dir():
            raise ValueError("Repository path must be a directory.")

        if not (self.repository / ".git").exists():
            raise ValueError("The supplied path is not a Git repository.")

    def _run_git(self, arguments: list[str]) -> str:
        """Run a Git command and return its text output."""

        result = subprocess.run(
            ["git", *arguments],
            cwd=self.repository,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        if result.returncode != 0:
            raise ValueError(
                result.stderr.strip() or "Git command failed."
            )

        return result.stdout

    def _run_git_bytes(self, arguments: list[str]) -> bytes:
        """Run a Git command and return its raw byte output."""

        result = subprocess.run(
            ["git", *arguments],
            cwd=self.repository,
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            raise ValueError(
                result.stderr.decode("utf-8", errors="replace").strip()
                or "Git command failed."
            )

        return result.stdout

    @staticmethod
    def _normalize_content(content: bytes) -> bytes:
        """Normalize line endings before comparing file contents."""

        return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    def _is_excluded(self, file_path: str) -> bool:
        """Return True for sensitive or generated files."""

        path = Path(file_path.replace("\\", "/"))

        parts = {part.lower() for part in path.parts}
        filename = path.name.lower()
        suffix = path.suffix.lower()

        if parts.intersection(self.EXCLUDED_DIRS):
            return True

        if filename in self.EXCLUDED_FILES:
            return True

        if filename.startswith(".env."):
            return True

        if suffix in self.EXCLUDED_SUFFIXES:
            return True

        return False

    def _validate_reference(self, reference: str) -> None:
        """Ensure the supplied Git reference resolves to a commit."""

        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("Git reference must be a non-empty string.")

        self._run_git([
            "rev-parse",
            "--verify",
            "--quiet",
            "--end-of-options",
            f"{reference}^{{commit}}",
        ])

    def _parse_git_status(self) -> list[dict]:
        """Parse Git porcelain status output."""

        output = self._run_git([
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ])

        # Re-run in binary mode to preserve Git's NUL-delimited paths.
        raw_output = self._run_git_bytes([
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ])

        entries = raw_output.split(b"\0")
        changes = []
        index = 0

        while index < len(entries):
            entry = entries[index]
            index += 1

            if not entry:
                continue

            if len(entry) < 4:
                continue

            status_code = entry[:2].decode("ascii", errors="replace")
            file_path = entry[3:].decode("utf-8", errors="replace")

            old_path = None

            if "R" in status_code or "C" in status_code:
                if index < len(entries):
                    old_path = entries[index].decode(
                        "utf-8",
                        errors="replace",
                    )
                    index += 1

            if status_code == "??":
                status = "added"
            elif "R" in status_code:
                status = "renamed"
            elif "C" in status_code:
                status = "copied"
            elif "D" in status_code:
                status = "deleted"
            elif "A" in status_code:
                status = "added"
            else:
                status = "modified"

            if self._is_excluded(file_path):
                continue

            if old_path and self._is_excluded(old_path):
                continue

            change = {
                "path": file_path,
                "status": status,
            }

            if old_path:
                change["old_path"] = old_path

            changes.append(change)

        return changes

    def _detect_unstaged_renames(
        self,
        changes: list[dict],
        baseline: str,
    ) -> list[dict]:
        """Correlate deleted and added files with identical content."""

        deleted = [
            item for item in changes
            if item["status"] == "deleted"
        ]

        added = [
            item for item in changes
            if item["status"] == "added"
        ]

        matched_added = set()
        matched_deleted = set()
        renamed_changes = []

        for old_change in deleted:
            old_path = old_change["path"]

            try:
                old_content = self._run_git_bytes([
                    "show",
                    f"{baseline}:{old_path}",
                ])
            except ValueError:
                continue

            old_hash = hashlib.sha256(
                self._normalize_content(old_content)
            ).digest()

            for index, new_change in enumerate(added):
                if index in matched_added:
                    continue

                new_path = new_change["path"]

                try:
                    new_content = (
                        self.repository / new_path
                    ).read_bytes()
                except OSError:
                    continue

                new_hash = hashlib.sha256(
                    self._normalize_content(new_content)
                ).digest()

                if old_hash == new_hash:
                    renamed_changes.append({
                        "path": new_path,
                        "old_path": old_path,
                        "status": "renamed",
                    })

                    matched_added.add(index)
                    matched_deleted.add(id(old_change))
                    break

        remaining_changes = [
            item
            for item in changes
            if id(item) not in matched_deleted
            and not (
                item["status"] == "added"
                and any(
                    added[index] is item
                    for index in matched_added
                )
            )
        ]

        return remaining_changes + renamed_changes

    @staticmethod
    def _build_summary(changes: list[dict]) -> dict:
        """Build change counts for the report."""

        summary = {
            "total_changes": len(changes),
            "added": 0,
            "modified": 0,
            "deleted": 0,
            "renamed": 0,
            "copied": 0,
        }

        for change in changes:
            status = change["status"]

            if status in summary:
                summary[status] += 1

        return summary

    def analyze(self, baseline: str = "HEAD") -> dict:
        """Analyze working-tree changes against a valid Git baseline."""

        self._validate_reference(baseline)

        changes = self._parse_git_status()

        changes = self._detect_unstaged_renames(
            changes,
            baseline,
        )

        changes.sort(
            key=lambda item: (
                item["path"],
                item["status"],
            )
        )

        return {
            "baseline": baseline,
            "changes": changes,
            "summary": self._build_summary(changes),
        }
