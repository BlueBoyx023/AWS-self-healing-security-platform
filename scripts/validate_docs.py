

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STATUS_FILE = PROJECT_ROOT / "documentation" / "project_status.json"
TEST_RESULTS_FILE = PROJECT_ROOT / "documentation" / "test_results.json"
INVENTORY_FILE = PROJECT_ROOT / "docs" / "generated" / "documentation_inventory.md"

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

ERRORS = []
WARNINGS = []


def check_file(path: Path, description: str) -> None:
    if not path.is_file():
        try:
            display_path = path.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = path

        ERRORS.append(f"{description} missing: {display_path}")


def validate_project_status() -> None:
    check_file(STATUS_FILE, "Project status registry")

    if not STATUS_FILE.exists():
        return

    try:
        data = json.loads(STATUS_FILE.read_text(encoding="utf-8-sig"))

        if not isinstance(data, dict):
            ERRORS.append("Project status must contain a JSON object.")
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

    except (json.JSONDecodeError, OSError) as error:
        ERRORS.append(f"Project status JSON error: {error}")


def validate_test_results() -> None:
    check_file(TEST_RESULTS_FILE, "Test results report")

    if not TEST_RESULTS_FILE.exists():
        return

    try:
        data = json.loads(
            TEST_RESULTS_FILE.read_text(encoding="utf-8-sig")
        )

        if not isinstance(data, dict):
            ERRORS.append("Test results must contain a JSON object.")
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

        counts = data.get("test_counts", {})
        subtests = data.get("subtest_counts", {})
        junit = data.get("junit_counts", {})

        if not isinstance(counts, dict):
            ERRORS.append("Main test counts must be an object.")
            return

        if not isinstance(subtests, dict):
            ERRORS.append("Subtest counts must be an object.")
            return

        if not isinstance(junit, dict):
            ERRORS.append("JUnit counts must be an object.")
            return

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

        for field in ["passed", "failed"]:
            if field not in subtests:
                ERRORS.append(
                    f"Missing subtest count: {field}"
                )

        if junit.get("total") is None:
            ERRORS.append("JUnit total count is missing.")

        # Validate that all reported counts are non-negative integers.
        count_values = {}

        for category, source in [
            ("main", counts),
            ("subtest", subtests),
            ("JUnit", junit),
        ]:
            fields = (
                required_counts
                if category == "main"
                else ["passed", "failed"]
                if category == "subtest"
                else ["total", "failures", "errors", "skipped"]
            )

            for field in fields:
                value = source.get(field)

                if (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value < 0
                ):
                    ERRORS.append(
                        f"Invalid {category} test count: {field}"
                    )
                else:
                    count_values[(category, field)] = value

        if (
            data.get("status") == "passed"
            and data.get("exit_code") != 0
        ):
            ERRORS.append(
                "Test report status conflicts with exit code."
            )

        if (
            data.get("status") == "passed"
            and (
                counts.get("failed", 0) > 0
                or counts.get("errors", 0) > 0
            )
        ):
            ERRORS.append(
                "Passing report contains failed tests or errors."
            )

        # Main test counts and subtest counts must reconcile
        # with the total number of JUnit test cases.
        main_fields = [
            "passed",
            "failed",
            "errors",
            "skipped",
            "xfailed",
            "xpassed",
        ]

        main_total = 0
        main_counts_valid = True

        for field in main_fields:
            value = counts.get(field, 0)

            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                main_counts_valid = False
                break

            main_total += value

        subtest_total = 0
        subtest_counts_valid = True

        for field in ["passed", "failed"]:
            value = subtests.get(field, 0)

            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                subtest_counts_valid = False
                break

            subtest_total += value

        junit_total = junit.get("total")

        if (
            main_counts_valid
            and subtest_counts_valid
            and isinstance(junit_total, int)
            and not isinstance(junit_total, bool)
            and junit_total >= 0
        ):
            reported_total = main_total + subtest_total

            if reported_total != junit_total:
                ERRORS.append(
                    "Test count mismatch: main tests plus subtests "
                    f"({reported_total}) do not match JUnit total "
                    f"({junit_total})."
                )

        # A passing full-suite report is the evidence represented by the
        # project's last verified checkpoint. Failed runs do not advance it.
        if data.get("status") == "passed" and STATUS_FILE.exists():
            try:
                project_status = json.loads(
                    STATUS_FILE.read_text(encoding="utf-8-sig")
                )
                checkpoint = project_status.get("development", {}).get(
                    "last_verified_checkpoint"
                )
                completed_at = data.get("completed_at_utc")
                if isinstance(checkpoint, str) and isinstance(completed_at, str):
                    checkpoint_date = date.fromisoformat(checkpoint)
                    report_date = datetime.fromisoformat(
                        completed_at.replace("Z", "+00:00")
                    ).date()
                    if checkpoint_date != report_date:
                        ERRORS.append(
                            "Project last_verified_checkpoint date "
                            f"({checkpoint_date}) does not match the passing "
                            f"test report date ({report_date})."
                        )
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                ERRORS.append(
                    "Unable to compare project checkpoint date with test report date."
                )

    except (json.JSONDecodeError, OSError) as error:
        ERRORS.append(
            f"Test results JSON error: {error}"
        )


def validate_markdown_links() -> None:
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
        except (OSError, UnicodeDecodeError):
            WARNINGS.append(
                f"Could not read Markdown file: {relative}"
            )
            continue

        for match in pattern.finditer(content):
            raw_target = match.group(1).strip()

            # Ignore empty Markdown links safely.
            if not raw_target:
                continue

            target = raw_target.split()[0].strip("<>")

            if not target or target.startswith("#"):
                continue

            parsed = urlparse(target)

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
    ERRORS.clear()
    WARNINGS.clear()

    print("===== DOCUMENTATION VALIDATION =====")

    for relative_path in REQUIRED_FILES:
        check_file(
            PROJECT_ROOT / relative_path,
            "Required document",
        )

    check_file(
        INVENTORY_FILE,
        "Generated inventory",
    )

    validate_project_status()
    validate_test_results()
    validate_markdown_links()

    print(f"\nErrors: {len(ERRORS)}")
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
