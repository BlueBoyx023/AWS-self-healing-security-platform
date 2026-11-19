import json

import pytest

from scripts import validate_docs


@pytest.fixture(autouse=True)
def reset_validation_state():
    validate_docs.ERRORS.clear()
    validate_docs.WARNINGS.clear()

    yield

    validate_docs.ERRORS.clear()
    validate_docs.WARNINGS.clear()


def test_validator_module_imports():
    assert callable(validate_docs.main)


def test_project_status_rejects_invalid_json(tmp_path, monkeypatch):
    status_file = tmp_path / "project_status.json"
    status_file.write_text("{ invalid json", encoding="utf-8")

    monkeypatch.setattr(validate_docs, "STATUS_FILE", status_file)

    validate_docs.validate_project_status()

    assert any(
        "JSON error" in error
        for error in validate_docs.ERRORS
    )


def test_project_status_rejects_invalid_component(tmp_path, monkeypatch):
    status_file = tmp_path / "project_status.json"

    status_file.write_text(
        json.dumps({
            "schema_version": "1.0",
            "project": {},
            "development": {},
            "components": [{"id": "", "status": ""}],
            "security_controls": [],
            "production_requirements": [],
            "documentation": {
                "human_review_required": []
            },
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(validate_docs, "STATUS_FILE", status_file)

    validate_docs.validate_project_status()

    assert any(
        "Invalid component" in error
        for error in validate_docs.ERRORS
    )


def test_test_results_rejects_invalid_json(tmp_path, monkeypatch):
    results_file = tmp_path / "test_results.json"
    results_file.write_text("{ invalid json", encoding="utf-8")

    monkeypatch.setattr(
        validate_docs,
        "TEST_RESULTS_FILE",
        results_file,
    )

    validate_docs.validate_test_results()

    assert any(
        "JSON error" in error
        for error in validate_docs.ERRORS
    )


def test_test_results_rejects_passing_report_with_failures(
    tmp_path, monkeypatch
):
    results_file = tmp_path / "test_results.json"

    results_file.write_text(
        json.dumps({
            "status": "passed",
            "started_at_utc": "2026-11-19T09:00:00+00:00",
            "completed_at_utc": "2026-11-19T09:01:00+00:00",
            "exit_code": 0,
            "test_counts": {
                "passed": 90,
                "failed": 1,
                "errors": 0,
                "skipped": 0,
            },
            "subtest_counts": {
                "passed": 9,
                "failed": 0,
            },
            "junit_counts": {
                "total": 100,
                "failures": 1,
                "errors": 0,
                "skipped": 0,
            },
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        validate_docs,
        "TEST_RESULTS_FILE",
        results_file,
    )

    validate_docs.validate_test_results()

    assert any(
        "failed tests" in error
        for error in validate_docs.ERRORS
    )


def test_test_results_rejects_inconsistent_counts(
    tmp_path, monkeypatch
):
    results_file = tmp_path / "test_results.json"

    results_file.write_text(
        json.dumps({
            "status": "passed",
            "started_at_utc": "2026-11-19T09:00:00+00:00",
            "completed_at_utc": "2026-11-19T09:01:00+00:00",
            "exit_code": 0,
            "test_counts": {
                "passed": 90,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
            },
            "subtest_counts": {
                "passed": 9,
                "failed": 0,
            },
            "junit_counts": {
                "total": 100,
                "failures": 0,
                "errors": 0,
                "skipped": 0,
            },
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        validate_docs,
        "TEST_RESULTS_FILE",
        results_file,
    )

    validate_docs.validate_test_results()

    assert any(
        "count" in error.lower()
        for error in validate_docs.ERRORS
    )


def test_markdown_validator_handles_empty_link(tmp_path, monkeypatch):
    markdown_file = tmp_path / "README.md"

    markdown_file.write_text(
        "An empty link: []()",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        validate_docs,
        "PROJECT_ROOT",
        tmp_path,
    )

    validate_docs.validate_markdown_links()

    assert isinstance(validate_docs.ERRORS, list)


def test_markdown_validator_detects_broken_local_link(
    tmp_path, monkeypatch
):
    markdown_file = tmp_path / "README.md"

    markdown_file.write_text(
        "[Missing document](missing.md)",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        validate_docs,
        "PROJECT_ROOT",
        tmp_path,
    )

    validate_docs.validate_markdown_links()

    assert any(
        "Broken local link" in error
        for error in validate_docs.ERRORS
    )
