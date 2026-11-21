

from types import SimpleNamespace

import pytest

import scripts.devdoc.cli as cli_module
from scripts.devdoc.cli import create_parser, main


class MockProvider:
    pass


def test_parser_default_arguments():
    parser = create_parser()
    args = parser.parse_args([])

    assert args.repo == "."
    assert args.baseline == "HEAD"
    assert args.document_type == "technical documentation"
    assert args.max_file_bytes == 100_000
    assert args.max_total_bytes == 1_000_000
    assert args.model is None
    assert args.timeout == 60.0
    assert args.max_retries == 2
    assert args.max_context_bytes == 1_000_000


def test_parser_accepts_custom_arguments():
    parser = create_parser()

    args = parser.parse_args([
        "--repo", "test-repo",
        "--baseline", "HEAD~2",
        "--document-type", "security documentation",
        "--max-file-bytes", "50000",
        "--max-total-bytes", "500000",
    ])

    assert args.repo == "test-repo"
    assert args.baseline == "HEAD~2"
    assert args.document_type == "security documentation"
    assert args.max_file_bytes == 50_000
    assert args.max_total_bytes == 500_000


def test_parser_rejects_invalid_size_argument():
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--max-file-bytes", "invalid"])


def test_main_creates_default_openai_provider(monkeypatch, capsys):
    captured = {}
    provider = MockProvider()

    def create_provider(**kwargs):
        captured["provider_options"] = kwargs
        return provider

    class FakeOrchestrator:
        def __init__(self, **kwargs):
            captured["orchestrator_provider"] = kwargs["ai_provider"]

        def run(self, document_type):
            return {
                "context_summary": {},
                "draft": SimpleNamespace(content="# Overview\nDraft."),
                "review": SimpleNamespace(approved=True, issues=[], warnings=[]),
            }

    monkeypatch.setattr(cli_module, "OpenAIProvider", create_provider)
    monkeypatch.setattr(cli_module, "DevDocOrchestrator", FakeOrchestrator)

    result = main([
        "--model", "configured-model",
        "--timeout", "20",
        "--max-retries", "1",
        "--max-context-bytes", "2000",
    ])

    assert result == 0
    assert captured["provider_options"] == {
        "model": "configured-model",
        "timeout": 20.0,
        "max_retries": 1,
        "max_context_bytes": 2000,
    }
    assert captured["orchestrator_provider"] is provider
    assert "Written to disk: No" in capsys.readouterr().out


def test_main_runs_successfully(monkeypatch, capsys):
    expected_result = {
        "context_summary": {
            "collected_files": 2,
            "total_bytes": 500,
        },
        "draft": SimpleNamespace(
            content="# Overview\nGenerated documentation."
        ),
        "review": SimpleNamespace(
            approved=True,
            issues=[],
            warnings=[],
        ),
    }

    captured = {}

    class FakeOrchestrator:
        def __init__(
            self,
            repo_path,
            ai_provider,
            baseline,
            max_file_bytes,
            max_total_bytes,
        ):
            captured["repo_path"] = repo_path
            captured["provider"] = ai_provider
            captured["baseline"] = baseline

        def run(self, document_type):
            captured["document_type"] = document_type
            return expected_result

    monkeypatch.setattr(
        cli_module,
        "DevDocOrchestrator",
        FakeOrchestrator,
    )

    provider = MockProvider()

    result = main(
        [
            "--repo", "test-repo",
            "--baseline", "HEAD~1",
            "--document-type", "security documentation",
        ],
        provider=provider,
    )

    output = capsys.readouterr().out

    assert result == 0
    assert captured["repo_path"] == "test-repo"
    assert captured["provider"] is provider
    assert captured["baseline"] == "HEAD~1"
    assert captured["document_type"] == "security documentation"

    assert "GENERATED DOCUMENTATION DRAFT" in output
    assert "# Overview" in output
    assert "Human approval required: Yes" in output
    assert "Written to disk: No" in output


def test_main_handles_orchestrator_errors(monkeypatch, capsys):
    class FailingOrchestrator:
        def __init__(self, **kwargs):
            raise RuntimeError("Orchestration failed")

    monkeypatch.setattr(
        cli_module,
        "DevDocOrchestrator",
        FailingOrchestrator,
    )

    result = main([], provider=MockProvider())

    captured = capsys.readouterr()

    assert result == 1
    assert "DevDoc error: Orchestration failed" in captured.err


def test_main_reports_review_issues_and_warnings(monkeypatch, capsys):
    class FakeOrchestrator:
        def __init__(self, **kwargs):
            pass

        def run(self, document_type):
            return {
                "context_summary": {},
                "draft": SimpleNamespace(content="# Overview\nDraft."),
                "review": SimpleNamespace(
                    approved=False,
                    issues=["Missing required section: Testing"],
                    warnings=["Draft is very short"],
                ),
            }

    monkeypatch.setattr(
        cli_module,
        "DevDocOrchestrator",
        FakeOrchestrator,
    )

    result = main([], provider=MockProvider())
    output = capsys.readouterr().out

    assert result == 0
    assert "Structural checks passed: False" in output
    assert "ISSUE: Missing required section: Testing" in output
    assert "WARNING: Draft is very short" in output


def test_main_does_not_save_documentation(monkeypatch, capsys):
    class FakeOrchestrator:
        def __init__(self, **kwargs):
            pass

        def run(self, document_type):
            return {
                "context_summary": {},
                "draft": SimpleNamespace(content="# Overview\nDraft."),
                "review": SimpleNamespace(
                    approved=True,
                    issues=[],
                    warnings=[],
                ),
            }

    monkeypatch.setattr(
        cli_module,
        "DevDocOrchestrator",
        FakeOrchestrator,
    )

    main([], provider=MockProvider())
    output = capsys.readouterr().out

    assert "Written to disk: No" in output


def test_main_returns_zero_when_review_has_warnings(monkeypatch):
    class FakeOrchestrator:
        def __init__(self, **kwargs):
            pass

        def run(self, document_type):
            return {
                "context_summary": {},
                "draft": SimpleNamespace(content="# Overview\nDraft."),
                "review": SimpleNamespace(
                    approved=True,
                    issues=[],
                    warnings=["Verify technical claims"],
                ),
            }

    monkeypatch.setattr(
        cli_module,
        "DevDocOrchestrator",
        FakeOrchestrator,
    )

    result = main([], provider=MockProvider())

    assert result == 0
