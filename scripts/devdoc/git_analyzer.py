

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

    def _validate_reference(self, reference: str) -> str:
        """Ensure the supplied Git reference resolves to a commit."""

        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("Git reference must be a non-empty string.")

        return self._run_git([
            "rev-parse",
            "--verify",
            "--quiet",
            "--end-of-options",
            f"{reference}^{{commit}}",
        ]).strip()

    def _parse_diff(self, baseline: str) -> list[dict]:
        """Parse tracked changes from a baseline tree to the worktree."""

        raw_output = self._run_git_bytes([
            "diff",
            "--name-status",
            "-z",
            "--find-renames",
            "--find-copies",
            "--no-ext-diff",
            baseline,
            "--",
        ])

        entries = raw_output.split(b"\0")
        changes = []
        index = 0

        while index < len(entries):
            status_entry = entries[index]
            index += 1

            if not status_entry:
                continue

            status_code = status_entry.decode("ascii", errors="replace")
            if not status_code:
                continue

            if index >= len(entries):
                break

            first_path = entries[index].decode("utf-8", errors="replace")
            index += 1
            old_path = None

            if status_code.startswith(("R", "C")):
                if index >= len(entries):
                    break
                file_path = entries[index].decode("utf-8", errors="replace")
                index += 1
                old_path = first_path
                status = "renamed" if status_code.startswith("R") else "copied"
            else:
                file_path = first_path
                code = status_code[0]
                if code == "A":
                    status = "added"
                elif code == "D":
                    status = "deleted"
                else:
                    status = "modified"

            if not self._is_valid_repo_path(file_path) or self._is_excluded(file_path):
                continue

            if old_path and (
                not self._is_valid_repo_path(old_path)
                or self._is_excluded(old_path)
            ):
                continue

            change = {
                "path": file_path,
                "status": status,
            }

            if old_path:
                change["old_path"] = old_path

            changes.append(change)

        return changes

    def _parse_untracked_files(self) -> list[dict]:
        """Return safe, non-ignored untracked files without duplicate paths."""

        raw_output = self._run_git_bytes([
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        ])

        changes = []
        for raw_path in raw_output.split(b"\0"):
            if not raw_path:
                continue
            file_path = raw_path.decode("utf-8", errors="replace")
            if (
                self._is_valid_repo_path(file_path)
                and not self._is_excluded(file_path)
            ):
                changes.append({"path": file_path, "status": "added"})
        return changes

    @staticmethod
    def _is_valid_repo_path(file_path: str) -> bool:
        """Reject paths that are absolute or lexically escape the repository."""

        if not isinstance(file_path, str) or not file_path or "\0" in file_path:
            return False

        normalized = file_path.replace("\\", "/")
        path = Path(normalized)
        return not path.is_absolute() and ".." not in path.parts

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
                    candidate = self.repository / new_path
                    resolved = candidate.resolve(strict=True)
                    resolved.relative_to(self.repository)
                    if not resolved.is_file() or candidate.is_symlink():
                        continue
                    new_content = resolved.read_bytes()
                except (OSError, ValueError):
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
        """Analyze worktree changes since the baseline's merge base with HEAD.

        Tracked changes include commits on the current branch and staged or
        unstaged edits. Eligible untracked files are added separately.
        """

        baseline_commit = self._validate_reference(baseline)
        head_commit = self._validate_reference("HEAD")
        merge_base = self._run_git([
            "merge-base",
            baseline_commit,
            head_commit,
        ]).strip()

        changes = self._parse_diff(merge_base)
        tracked_paths = {change["path"] for change in changes}
        changes.extend(
            change
            for change in self._parse_untracked_files()
            if change["path"] not in tracked_paths
        )

        changes = self._detect_unstaged_renames(
            changes,
            merge_base,
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
