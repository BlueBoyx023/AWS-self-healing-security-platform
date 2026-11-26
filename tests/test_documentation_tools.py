
import json

import pytest

from scripts import generate_docs, validate_docs


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


def test_passing_report_accepts_different_project_checkpoint_date(
    tmp_path, monkeypatch
):
    status_file = tmp_path / "project_status.json"

    status_file.write_text(
        json.dumps({
            "development": {
                "last_verified_checkpoint": "2026-11-19"
            }
        }),
        encoding="utf-8",
    )

    results_file = tmp_path / "test_results.json"

    results_file.write_text(
        json.dumps({
            "status": "passed",
            "started_at_utc": "2026-11-22T09:00:00+00:00",
            "completed_at_utc": "2026-11-22T09:01:00+00:00",
            "exit_code": 0,
            "test_counts": {
                "passed": 1,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
            },
            "subtest_counts": {
                "passed": 0,
                "failed": 0,
            },
            "junit_counts": {
                "total": 1,
                "failures": 0,
                "errors": 0,
                "skipped": 0,
            },
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        validate_docs,
        "STATUS_FILE",
        status_file,
    )

    monkeypatch.setattr(
        validate_docs,
        "TEST_RESULTS_FILE",
        results_file,
    )

    validate_docs.validate_test_results()

    assert validate_docs.ERRORS == []


def test_inventory_does_not_overwrite_manual_security_documents(
    tmp_path, monkeypatch
):
    docs_dir = tmp_path / "docs"
    generated_dir = docs_dir / "generated"
    generated_dir.mkdir(parents=True)

    security_doc = docs_dir / "security-design.md"
    original_content = (
        "# Human maintained security design\n\nReview required.\n"
    )
    security_doc.write_text(original_content, encoding="utf-8")

    (tmp_path / "documentation").mkdir()

    status_file = tmp_path / "documentation" / "project_status.json"

    status_file.write_text(
        json.dumps({
            "documentation": {
                "human_review_required": ["docs/security-design.md"]
            }
        }),
        encoding="utf-8",
    )

    (tmp_path / ".pytest-tmp-fixture").mkdir()

    (tmp_path / ".pytest-tmp-fixture" / "README.md").write_text(
        "# Test fixture, not a project document\n",
        encoding="utf-8",
    )

    output_file = generated_dir / "documentation_inventory.md"

    monkeypatch.setattr(generate_docs, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(generate_docs, "STATUS_FILE", status_file)
    monkeypatch.setattr(generate_docs, "OUTPUT_FILE", output_file)

    generate_docs.generate_inventory()

    assert security_doc.read_text(encoding="utf-8") == original_content

    inventory = output_file.read_text(encoding="utf-8")

    assert "docs/security-design.md" in inventory
    assert ".pytest-tmp-fixture" not in inventory


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


def test_markdown_validator_ignores_pytest_temporary_directories(
    tmp_path, monkeypatch
):
    temporary_dir = tmp_path / ".pytest-tmp-fixture"
    temporary_dir.mkdir()

    (temporary_dir / "README.md").write_text(
        "[Fixture link](missing.md)",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        validate_docs,
        "PROJECT_ROOT",
        tmp_path,
    )

    validate_docs.validate_markdown_links()

    assert validate_docs.ERRORS == []
