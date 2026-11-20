

from __future__ import annotations

import re
from pathlib import Path


class ChangeClassifier:
    """Classify Git changes using deterministic file-path rules."""

    SECURITY_KEYWORDS = {
        "security",
        "remediation",
        "validator",
        "verification",
        "threat",
        "audit",
        "encryption",
        "cryptography",
        "authentication",
        "authorization",
        "idempotency",
    }

    IAM_KEYWORDS = {
        "iam",
        "permission",
        "permissions",
        "policy",
        "policies",
        "role",
        "roles",
        "trust",
        "accesscontrol",
    }

    AWS_KEYWORDS = {
        "aws",
        "s3",
        "kms",
        "cloudwatch",
        "lambda",
        "ec2",
        "dynamodb",
        "sns",
        "sqs",
        "eventbridge",
        "cloudtrail",
        "guardduty",
        "securityhub",
        "secretsmanager",
        "sts",
        "vpc",
    }

    CONFIG_SUFFIXES = {
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
    }

    CONFIG_FILES = {
        "dockerfile",
        "requirements.txt",
        "pyproject.toml",
        "pytest.ini",
        "setup.cfg",
        "settings.py",
    }

    DOCUMENTATION_SUFFIXES = {
        ".md",
        ".rst",
        ".adoc",
    }

    def _get_tokens(self, file_path: str) -> set[str]:
        """Extract searchable tokens from a file path."""

        normalized = file_path.replace("\\", "/").lower()

        return set(
            re.split(r"[^a-z0-9]+", normalized)
        ) - {""}

    def _classify_file(self, file_path: str) -> list[dict]:
        """Return all applicable classifications for a file."""

        path = Path(file_path.replace("\\", "/"))
        filename = path.name.lower()
        suffix = path.suffix.lower()
        tokens = self._get_tokens(file_path)
        classifications = []

        def add(category: str, reason: str) -> None:
            classifications.append({
                "category": category,
                "reason": reason,
            })

        # Test identification
        is_test = (
            "tests" in tokens
            or "test" in tokens
            or filename.startswith("test_")
            or "_test." in filename
        )

        if is_test:
            add("Tests", "File path or filename indicates a test.")

        # Security logic identification
        if tokens.intersection(self.SECURITY_KEYWORDS):
            add(
                "Security Logic",
                "File path or filename contains security-related keywords.",
            )

        # IAM and permissions identification
        if tokens.intersection(self.IAM_KEYWORDS):
            add(
                "IAM & Permissions",
                "File path or filename indicates access control or IAM.",
            )

        # AWS service identification
        if tokens.intersection(self.AWS_KEYWORDS):
            add(
                "AWS Services",
                "File path or filename contains AWS service keywords.",
            )

        # Configuration identification
        if (
            suffix in self.CONFIG_SUFFIXES
            or filename in self.CONFIG_FILES
            or "config" in tokens
            or "configuration" in tokens
        ):
            add(
                "Configuration",
                "File extension or filename indicates configuration.",
            )

        # Documentation identification
        if (
            suffix in self.DOCUMENTATION_SUFFIXES
            or "docs" in tokens
            or "documentation" in tokens
        ):
            add(
                "Documentation",
                "File path or extension indicates documentation.",
            )

        # Fallback classification
        if not classifications:
            add(
                "General Code",
                "No specific classification rule matched.",
            )

        return classifications

    def classify(self, analysis_report: dict) -> dict:
        """Classify files from a GitChangeAnalyzer report."""

        if not isinstance(analysis_report, dict):
            raise ValueError("Analysis report must be a dictionary.")

        changes = analysis_report.get("changes")

        if not isinstance(changes, list):
            raise ValueError("Analysis report must contain a changes list.")

        results = []
        category_counts = {}

        for change in changes:
            if not isinstance(change, dict):
                raise ValueError("Each change must be a dictionary.")

            file_path = change.get("path")
            status = change.get("status")

            if not isinstance(file_path, str) or not file_path.strip():
                raise ValueError("Each change must contain a valid path.")

            if not isinstance(status, str) or not status.strip():
                raise ValueError("Each change must contain a valid status.")

            classifications = self._classify_file(file_path)

            categories = [
                item["category"]
                for item in classifications
            ]

            for category in categories:
                category_counts[category] = (
                    category_counts.get(category, 0) + 1
                )

            results.append({
                "path": file_path,
                "status": status,
                "categories": categories,
                "reasons": classifications,
            })

        return {
            "baseline": analysis_report.get("baseline"),
            "classifications": results,
            "summary": {
                "total_files": len(results),
                "category_counts": category_counts,
            },
        }
