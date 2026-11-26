
from __future__ import annotations

import json
import re
import sys

from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]

STATUS_FILE = PROJECT_ROOT / "documentation" / "project_status.json"
TEST_RESULTS_FILE = PROJECT_ROOT / "documentation" / "test_results.json"
INVENTORY_FILE = (
    PROJECT_ROOT / "docs" / "generated" / "documentation_inventory.md"
)

REQUIRED_FILES = [
    "README.md",
    "PROJECT_STATUS.md",
    "docs/README.md",
    "docs/RESUME_CHECKPOINT.md",
    "docs/security-design.md",
    "docs/threat-model.md",
    "docs/devdoc-security.md",
    "tests/README.md",
    "tests/test_plan.md",
]

ERRORS: list[str] = []
WARNINGS: list[str] = []


def check_file(path: Path, description: str) -> None:
    """Verify that a required file exists."""

    if not path.is_file():
        try:
            display_path = path.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = path

        ERRORS.append(f"{description} missing: {display_path}")


def load_json_file(path: Path, description: str) -> dict | None:
    """Load a JSON object and report parsing errors."""

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))

        if not isinstance(data, dict):
            ERRORS.append(f"{description} must contain a JSON object.")
            return None

        return data

    except json.JSONDecodeError as error:
        ERRORS.append(f"{description} JSON error: {error}")

    except OSError as error:
        ERRORS.append(f"Unable to read {description}: {error}")

    return None


def parse_iso_date(value: object, description: str) -> date | None:
    """Validate and parse an ISO 8601 calendar date."""

    if not isinstance(value, str):
        ERRORS.append(f"{description} must be an ISO date string.")
        return None

    try:
        return date.fromisoformat(value)

    except ValueError:
        ERRORS.append(f"{description} is not a valid ISO date: {value}")
        return None


def parse_iso_datetime(
    value: object,
    description: str,
) -> datetime | None:
    """Validate an ISO 8601 timestamp with an explicit timezone."""

    if not isinstance(value, str):
        ERRORS.append(f"{description} must be an ISO timestamp string.")
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None or parsed.utcoffset() is None:
            ERRORS.append(
                f"{description} must include a timezone."
            )
            return None

        return parsed

    except ValueError:
        ERRORS.append(
            f"{description} is not a valid ISO timestamp: {value}"
        )
        return None


def is_non_negative_integer(value: object) -> bool:
    """Return whether a value is a non-negative integer."""

    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    )


def validate_project_status() -> None:
    """Validate the project status registry."""

    check_file(STATUS_FILE, "Project status registry")

    if not STATUS_FILE.exists():
        return

    data = load_json_file(STATUS_FILE, "Project status")

    if data is None:
        return

    required_sections = [
        "schema_version",
        "project",
        "development",
        "components",
        "security_controls",
        "production_requirements",
        "documentation",
    ]

    for section in required_sections:
        if section not in data:
            ERRORS.append(
                f"Missing project status field: {section}"
            )

    development = data.get("development")

    if isinstance(development, dict):
        checkpoint = development.get("last_verified_checkpoint")

        if checkpoint is not None:
            parse_iso_date(
                checkpoint,
                "Project last_verified_checkpoint",
            )
        else:
            ERRORS.append(
                "Project last_verified_checkpoint is missing."
            )
    elif development is not None:
        ERRORS.append(
            "Project development section must be an object."
        )

    documentation = data.get("documentation", {})

    if isinstance(documentation, dict):
        review_files = documentation.get(
            "human_review_required", []
        )

        if isinstance(review_files, list):
            for relative_path in review_files:
                if isinstance(relative_path, str):
                    check_file(
                        PROJECT_ROOT / relative_path,
                        "Human-review document",
                    )
                else:
                    ERRORS.append(
                        "Invalid human-review document path."
                    )
        else:
            ERRORS.append(
                "Human-review documents must be a list."
            )

    elif documentation is not None:
        ERRORS.append(
            "Project documentation section must be an object."
        )

    components = data.get("components", [])

    if isinstance(components, list):
        for component in components:
            if (
                not isinstance(component, dict)
                or not component.get("id")
                or not component.get("status")
            ):
                ERRORS.append(
                    "Invalid component entry in project registry."
                )
    else:
        ERRORS.append(
            "Project components must be a list."
        )

    security_controls = data.get("security_controls", [])

    if not isinstance(security_controls, list):
        ERRORS.append(
            "Project security_controls must be a list."
        )
    else:
        for control in security_controls:
            if (
                not isinstance(control, dict)
                or not control.get("id")
                or not control.get("status")
            ):
                ERRORS.append(
                    "Invalid security control entry in project registry."
                )

    production_requirements = data.get(
        "production_requirements", []
    )

    if not isinstance(production_requirements, list):
        ERRORS.append(
            "Project production_requirements must be a list."
        )
    else:
        for requirement in production_requirements:
            if (
                not isinstance(requirement, dict)
                or not requirement.get("id")
                or not requirement.get("status")
            ):
                ERRORS.append(
                    "Invalid production requirement entry."
                )


def validate_test_results() -> None:
    """Validate test execution evidence and reported test counts."""

    check_file(TEST_RESULTS_FILE, "Test results report")

    if not TEST_RESULTS_FILE.exists():
        return

    data = load_json_file(TEST_RESULTS_FILE, "Test results")

    if data is None:
        return

    required_fields = [
        "status",
        "started_at_utc",
        "completed_at_utc",
        "exit_code",
        "test_counts",
        "subtest_counts",
        "junit_counts",
    ]

    for field in required_fields:
        if field not in data:
            ERRORS.append(
                f"Missing test report field: {field}"
            )

    # Validate test execution status and exit code.

    status = data.get("status")
    exit_code = data.get("exit_code")

    if status not in ("passed", "failed"):
        ERRORS.append(
            "Test report status must be 'passed' or 'failed'."
        )

    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        ERRORS.append(
            "Test report exit_code must be an integer."
        )
    elif status == "passed" and exit_code != 0:
        ERRORS.append(
            "Passing test report must have exit code 0."
        )
    elif status == "failed" and exit_code == 0:
        ERRORS.append(
            "Failed test report must have a non-zero exit code."
        )

    # Validate test execution timestamps independently.

    started_at = parse_iso_datetime(
        data.get("started_at_utc"),
        "Test report started_at_utc",
    )

    completed_at = parse_iso_datetime(
        data.get("completed_at_utc"),
        "Test report completed_at_utc",
    )

    if (
        started_at is not None
        and completed_at is not None
        and completed_at < started_at
    ):
        ERRORS.append(
            "Test report completion timestamp precedes its start timestamp."
        )

    # Load test count sections.

    counts = data.get("test_counts", {})
    subtests = data.get("subtest_counts", {})
    junit = data.get("junit_counts", {})

    if not isinstance(counts, dict):
        ERRORS.append(
            "Main test counts must be an object."
        )
        return

    if not isinstance(subtests, dict):
        ERRORS.append(
            "Subtest counts must be an object."
        )
        return

    if not isinstance(junit, dict):
        ERRORS.append(
            "JUnit counts must be an object."
        )
        return

    # Required main test count fields.

    required_counts = [
        "passed",
        "failed",
        "errors",
        "skipped",
    ]

    for field in required_counts:
        if field not in counts:
            ERRORS.append(
                f"Missing main test count: {field}"
            )

    # Required subtest count fields.

    for field in ["passed", "failed"]:
        if field not in subtests:
            ERRORS.append(
                f"Missing subtest count: {field}"
            )

    if junit.get("total") is None:
        ERRORS.append(
            "JUnit total count is missing."
        )

    # Validate all reported counts as non-negative integers.

    count_sections = [
        (
            "main",
            counts,
            [
                "passed",
                "failed",
                "errors",
                "skipped",
                "xfailed",
                "xpassed",
            ],
        ),
        (
            "subtest",
            subtests,
            ["passed", "failed"],
        ),
        (
            "JUnit",
            junit,
            ["total", "failures", "errors", "skipped"],
        ),
    ]

    for category, source, fields in count_sections:
        for field in fields:
            # Optional main test counts default to zero.
            if category == "main" and field not in source:
                continue

            value = source.get(field)

            if not is_non_negative_integer(value):
                ERRORS.append(
                    f"Invalid {category} test count: {field}"
                )

    # A passing report cannot contain failures or errors.

    if status == "passed":
        if counts.get("failed", 0) > 0:
            ERRORS.append(
                "Passing report contains failed tests."
            )

        if counts.get("errors", 0) > 0:
            ERRORS.append(
                "Passing report contains test errors."
            )

        if junit.get("failures", 0) > 0:
            ERRORS.append(
                "Passing report contains JUnit failures."
            )

        if junit.get("errors", 0) > 0:
            ERRORS.append(
                "Passing report contains JUnit errors."
            )

    # Reconcile main tests and subtests against JUnit totals.

    main_fields = [
        "passed",
        "failed",
        "errors",
        "skipped",
        "xfailed",
        "xpassed",
    ]

    main_counts_valid = all(
        is_non_negative_integer(counts.get(field, 0))
        for field in main_fields
    )

    subtest_fields = ["passed", "failed"]

    subtest_counts_valid = all(
        is_non_negative_integer(subtests.get(field))
        for field in subtest_fields
    )

    junit_total = junit.get("total")

    if (
        main_counts_valid
        and subtest_counts_valid
        and is_non_negative_integer(junit_total)
    ):
        main_total = sum(
            counts.get(field, 0)
            for field in main_fields
        )

        subtest_total = sum(
            subtests.get(field, 0)
            for field in subtest_fields
        )

        reported_total = main_total + subtest_total

        if reported_total != junit_total:
            ERRORS.append(
                "Test count mismatch: main tests plus subtests "
                f"({reported_total}) do not match JUnit total "
                f"({junit_total})."
            )

    # IMPORTANT:
    # last_verified_checkpoint represents a project development
    # checkpoint. completed_at_utc represents an individual test run.
    #
    # They are independent timestamps and are NOT required to match.
    # Each value is validated separately above.
    #
    # CI may execute the same test suite on a later date without
    # changing the historical project checkpoint.


def validate_markdown_links() -> None:
    """Validate relative Markdown links throughout the repository."""

    pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")

    markdown_files = list(PROJECT_ROOT.rglob("*.md"))

    excluded = {
        ".git",
        ".venv",
        ".pytest_cache",
        "__pycache__",
    }

    for source in markdown_files:
        relative = source.relative_to(PROJECT_ROOT)

        if any(
            part in excluded or part.startswith(".pytest-tmp")
            for part in relative.parts
        ):
            continue

        try:
            content = source.read_text(encoding="utf-8-sig")

        except (OSError, UnicodeDecodeError) as error:
            WARNINGS.append(
                f"Could not read Markdown file {relative}: {error}"
            )
            continue

        for match in pattern.finditer(content):
            raw_target = match.group(1).strip()

            # Ignore empty Markdown links.

            if not raw_target:
                continue

            target = raw_target.split()[0].strip("<>")

            if not target or target.startswith("#"):
                continue

            parsed = urlparse(target)

            # External URLs are outside local link validation.

            if parsed.scheme or parsed.netloc:
                continue

            target_path = unquote(parsed.path)

            if not target_path:
                continue

            resolved = (
                source.parent / target_path
            ).resolve()

            if not resolved.exists():
                ERRORS.append(
                    f"Broken local link in {relative}: {target}"
                )


def main() -> int:
    """Execute all documentation validation checks."""

    ERRORS.clear()
    WARNINGS.clear()

    print("===== DOCUMENTATION VALIDATION =====")

    # Required repository documents.

    for relative_path in REQUIRED_FILES:
        check_file(
            PROJECT_ROOT / relative_path,
            "Required document",
        )

    # Generated documentation inventory.

    check_file(
        INVENTORY_FILE,
        "Generated inventory",
    )

    # Structured metadata and evidence validation.

    print("\nValidating project status...")
    validate_project_status()

    print("Validating test results...")
    validate_test_results()

    # Markdown integrity.

    print("Validating Markdown links...")
    validate_markdown_links()

    # Final validation report.

    print("\n===== VALIDATION SUMMARY =====")
    print(f"Errors: {len(ERRORS)}")
    print(f"Warnings: {len(WARNINGS)}")

    for error in ERRORS:
        print(f"[ERROR] {error}")

    for warning in WARNINGS:
        print(f"[WARNING] {warning}")

    if ERRORS:
        print("\nDocumentation validation FAILED.")
        return 1

    print("\nDocumentation validation PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
