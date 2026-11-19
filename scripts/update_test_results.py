from __future__ import annotations

import importlib.metadata
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = PROJECT_ROOT / "documentation" / "test_results.json"


def parse_junit_report(xml_path: Path) -> dict:
    """Preserve raw JUnit counts, including subtests."""

    root = ET.parse(xml_path).getroot()
    suites = list(root.iter("testsuite"))

    if not suites:
        raise RuntimeError("No test suites found in JUnit XML.")

    totals = {
        "total": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "duration_seconds": 0.0,
    }

    for suite in suites:
        totals["total"] += int(suite.get("tests", 0))
        totals["failures"] += int(suite.get("failures", 0))
        totals["errors"] += int(suite.get("errors", 0))
        totals["skipped"] += int(suite.get("skipped", 0))
        totals["duration_seconds"] += float(suite.get("time", 0))

    totals["duration_seconds"] = round(
        totals["duration_seconds"], 3
    )

    return totals


def parse_console_summary(output: str) -> dict:
    """Extract main pytest counts without counting subtests."""

    summary_line = None

    for line in reversed(output.splitlines()):
        if re.search(r"\bin\s+[\d.]+s\b", line):
            summary_line = line.strip()
            break

    if summary_line is None:
        raise RuntimeError("Pytest console summary not found.")

    counts = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
    }

    for match in re.finditer(
        r"(\d+)\s+(passed|failed|errors?|skipped|xfailed|xpassed)\b",
        summary_line,
        re.IGNORECASE,
    ):
        value = int(match.group(1))
        category = match.group(2).lower()

        if category in ("error", "errors"):
            category = "errors"

        counts[category] += value

    counts["summary"] = summary_line

    return counts


def extract_subtests(output: str) -> dict:
    """Extract subtest counts from pytest console output."""

    patterns = {
        "passed": r"(\d+)\s+subtests?\s+passed",
        "failed": r"(\d+)\s+subtests?\s+failed",
    }

    results = {}

    for status, pattern in patterns.items():
        match = re.search(pattern, output, re.IGNORECASE)
        results[status] = int(match.group(1)) if match else 0

    return results


def main() -> int:
    started_at = datetime.now(timezone.utc)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        xml_path = Path(temp_dir) / "pytest-results.xml"

        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"--junitxml={xml_path}",
        ]

        print("Running automated test suite...")

        process = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        combined_output = process.stdout + "\n" + process.stderr
        print(combined_output.strip())

        if not xml_path.exists():
            print("ERROR: Pytest did not generate JUnit XML.")
            return process.returncode or 1

        try:
            junit_counts = parse_junit_report(xml_path)
            test_counts = parse_console_summary(combined_output)
        except (ET.ParseError, RuntimeError, ValueError) as error:
            print(f"ERROR: Unable to parse test results: {error}")
            return 1

    completed_at = datetime.now(timezone.utc)

    report = {
        "schema_version": "1.0",
        "status": "passed" if process.returncode == 0 else "failed",
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": completed_at.isoformat(),
        "python_version": sys.version.split()[0],
        "pytest_version": importlib.metadata.version("pytest"),
        "command": "python -m pytest -q",
        "exit_code": process.returncode,
        "test_counts": test_counts,
        "subtest_counts": extract_subtests(combined_output),
        "junit_counts": junit_counts,
    }

    temporary_output = OUTPUT_FILE.with_suffix(".json.tmp")

    temporary_output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    temporary_output.replace(OUTPUT_FILE)

    print("\n===== TEST REPORT GENERATED =====")
    print(f"File: {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Status: {report['status']}")
    print(f"Main tests passed: {test_counts['passed']}")
    print(f"Main tests failed: {test_counts['failed']}")
    print(f"Subtests passed: {report['subtest_counts']['passed']}")
    print(f"JUnit total cases: {junit_counts['total']}")

    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
