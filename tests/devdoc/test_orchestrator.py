

import pytest

import scripts.devdoc.orchestrator as orchestrator_module
from scripts.devdoc.ai_provider import AIProvider, AIResponse
from scripts.devdoc.documentation_reviewer import ReviewResult
from scripts.devdoc.orchestrator import DevDocOrchestrator


class MockProvider(AIProvider):
    def __init__(self):
        super().__init__()

    def _generate(self, request):
        return AIResponse(
            content=(
                "# Overview\n"
                "Project overview details.\n\n"
                "# Implementation\n"
                "Implementation details.\n\n"
                "# Testing\n"
                "Testing details."
            ),
            provider="mock",
            model="test-model",
        )


def test_orchestrator_initializes():
    orchestrator = DevDocOrchestrator(
        repo_path=".",
        ai_provider=MockProvider(),
    )

    assert orchestrator.git_analyzer is not None
    assert orchestrator.change_classifier is not None
    assert orchestrator.context_builder is not None
    assert orchestrator.draft_generator is not None
    assert orchestrator.documentation_reviewer is not None


def test_orchestrator_runs_complete_workflow(monkeypatch):
    calls = []

    change_report = {
        "baseline": "HEAD",
        "changes": [{"path": "example.py", "status": "modified"}],
        "summary": {"modified": 1},
    }

    classification_report = {
        "baseline": "HEAD",
        "classifications": [
            {
                "path": "example.py",
                "status": "modified",
                "categories": ["General Code"],
                "reasons": [],
            }
        ],
        "summary": {"total_files": 1},
    }

    context = {
        "files": [{"path": "example.py", "content": "print('test')"}],
        "summary": {"collected_files": 1},
    }

    draft = AIResponse(
        content=("# Overview\n" + ("Project details. " * 10)
                 + "\n# Security Considerations\nDetails.\n# Testing\nTests."),
        provider="mock",
        model="test-model",
    )

    review = ReviewResult(
        approved=True,
        issues=[],
        warnings=[],
        sections_found=["Overview"],
    )

    class FakeGitAnalyzer:
        def __init__(self, repo_path):
            calls.append(("git_init", repo_path))

        def analyze(self, baseline):
            calls.append(("analyze", baseline))
            return change_report

    class FakeClassifier:
        def __init__(self):
            calls.append(("classifier_init",))

        def classify(self, report):
            calls.append(("classify", report))
            return classification_report

    class FakeContextBuilder:
        def __init__(self, repo_path, max_file_bytes, max_total_bytes):
            calls.append(
                ("context_init", repo_path, max_file_bytes, max_total_bytes)
            )

        def build(self, report):
            calls.append(("build_context", report))
            return context

    class FakeDraftGenerator:
        def __init__(self, provider):
            calls.append(("draft_init", provider))

        def generate_draft(self, context, document_type):
            calls.append(("generate", context, document_type))
            return draft

    class FakeReviewer:
        def __init__(self):
            calls.append(("reviewer_init",))

        def review(self, draft, document_type):
            calls.append(("review", draft, document_type))
            return review

    monkeypatch.setattr(
        orchestrator_module, "GitChangeAnalyzer", FakeGitAnalyzer
    )
    monkeypatch.setattr(
        orchestrator_module, "ChangeClassifier", FakeClassifier
    )
    monkeypatch.setattr(
        orchestrator_module, "ContextBuilder", FakeContextBuilder
    )
    monkeypatch.setattr(
        orchestrator_module, "DraftGenerator", FakeDraftGenerator
    )
    monkeypatch.setattr(
        orchestrator_module, "DocumentationReviewer", FakeReviewer
    )

    provider = MockProvider()

    orchestrator = DevDocOrchestrator(
        repo_path="test-repository",
        ai_provider=provider,
        baseline="HEAD~1",
        max_file_bytes=50_000,
        max_total_bytes=500_000,
    )

    result = orchestrator.run(
        document_type="security documentation"
    )

    assert result["changes"] == change_report
    assert result["classification"] == classification_report
    assert result["context_summary"] == context["summary"]
    assert result["draft"] == draft
    assert result["review"] == review
    assert result["requires_human_approval"] is True
    assert result["written_to_disk"] is False

    assert ("analyze", "HEAD~1") in calls
    assert ("classify", change_report) in calls
    assert ("build_context", classification_report) in calls
    assert (
        "generate",
        context,
        "security documentation",
    ) in calls
    assert (
        "review",
        draft.content,
        "security documentation",
    ) in calls


def test_orchestrator_uses_default_baseline(monkeypatch):
    captured = {}

    class FakeGitAnalyzer:
        def __init__(self, repo_path):
            pass

        def analyze(self, baseline):
            captured["baseline"] = baseline
            return {"baseline": baseline, "changes": []}

    class FakeClassifier:
        def classify(self, report):
            return {"classifications": [], "summary": {}}

    class FakeContextBuilder:
        def __init__(self, *args, **kwargs):
            pass

        def build(self, report):
            return {"files": [], "summary": {}}

    class FakeDraftGenerator:
        def __init__(self, provider):
            pass

        def generate_draft(self, context, document_type):
            return AIResponse(
                content=("# Overview\n" + ("Details. " * 20)
                         + "\n# Implementation\nDetails.\n# Testing\nTests."),
                provider="mock",
                model="test-model",
            )

    class FakeReviewer:
        def review(self, draft, document_type):
            return ReviewResult(approved=True)

    monkeypatch.setattr(
        orchestrator_module, "GitChangeAnalyzer", FakeGitAnalyzer
    )
    monkeypatch.setattr(
        orchestrator_module, "ChangeClassifier", FakeClassifier
    )
    monkeypatch.setattr(
        orchestrator_module, "ContextBuilder", FakeContextBuilder
    )
    monkeypatch.setattr(
        orchestrator_module, "DraftGenerator", FakeDraftGenerator
    )
    monkeypatch.setattr(
        orchestrator_module, "DocumentationReviewer", FakeReviewer
    )

    orchestrator = DevDocOrchestrator(".", MockProvider())
    orchestrator.run()

    assert captured["baseline"] == "HEAD"


def test_orchestrator_propagates_analysis_errors(monkeypatch):
    class FailingGitAnalyzer:
        def __init__(self, repo_path):
            pass

        def analyze(self, baseline):
            raise RuntimeError("Git analysis failed")

    monkeypatch.setattr(
        orchestrator_module, "GitChangeAnalyzer", FailingGitAnalyzer
    )

    orchestrator = DevDocOrchestrator(".", MockProvider())

    with pytest.raises(RuntimeError, match="Git analysis failed"):
        orchestrator.run()


def test_orchestrator_requires_valid_ai_provider():
    with pytest.raises(TypeError):
        DevDocOrchestrator(
            repo_path=".",
            ai_provider="invalid-provider",
        )


def test_orchestrator_never_claims_to_write_files():
    orchestrator = DevDocOrchestrator(
        repo_path=".",
        ai_provider=MockProvider(),
    )

    assert not hasattr(orchestrator, "write_documentation")
    assert not hasattr(orchestrator, "save_draft")


def test_invalid_output_never_reaches_normal_reviewer(monkeypatch):
    orchestrator = DevDocOrchestrator(".", MockProvider())
    orchestrator.git_analyzer.analyze = lambda baseline: {"changes": []}
    orchestrator.change_classifier.classify = lambda report: {"classifications": []}
    orchestrator.context_builder.build = lambda report: {"files": [], "summary": {}}
    orchestrator.draft_generator.generate_draft = lambda **kwargs: AIResponse(
        content=("# Overview\nDetails.\n# Implementation\nDetails.\n"
                 "# Testing\nTests.\n- sudo rm -rf /tmp/example"),
        provider="mock",
        model="test-model",
    )

    class ReviewerMustNotRun:
        def review(self, **kwargs):
            pytest.fail("invalid output reached the normal reviewer")

    orchestrator.documentation_reviewer = ReviewerMustNotRun()

    result = orchestrator.run()

    assert result["eligible_for_human_review"] is False
    assert result["review"].approved is False
    assert any("unauthorized command" in issue for issue in result["review"].issues)
