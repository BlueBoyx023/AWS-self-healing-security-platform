

"""Coordinate the DevDoc documentation workflow."""

from scripts.devdoc.change_classifier import ChangeClassifier
from scripts.devdoc.context_builder import ContextBuilder
from scripts.devdoc.documentation_reviewer import DocumentationReviewer
from scripts.devdoc.draft_generator import DraftGenerator
from scripts.devdoc.git_analyzer import GitChangeAnalyzer


class DevDocOrchestrator:
    """Coordinate change analysis, context building, drafting, and review."""

    def __init__(
        self,
        repo_path,
        ai_provider,
        baseline="HEAD",
        max_file_bytes=100_000,
        max_total_bytes=1_000_000,
    ):
        self.repo_path = repo_path
        self.baseline = baseline

        self.git_analyzer = GitChangeAnalyzer(repo_path)
        self.change_classifier = ChangeClassifier()
        self.context_builder = ContextBuilder(
            repo_path,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
        )
        self.draft_generator = DraftGenerator(ai_provider)
        self.documentation_reviewer = DocumentationReviewer()

    def run(self, document_type="technical documentation"):
        """Run the workflow and return drafts for human review."""

        # Step 1: Detect repository changes.
        change_report = self.git_analyzer.analyze(
            baseline=self.baseline
        )

        # Step 2: Classify detected changes.
        classification_report = self.change_classifier.classify(
            change_report
        )

        # Step 3: Build safe project context.
        context = self.context_builder.build(
            classification_report
        )

        # Step 4: Generate a documentation draft.
        draft = self.draft_generator.generate_draft(
            context=context,
            document_type=document_type,
        )

        # Step 5: Review the generated draft.
        review = self.documentation_reviewer.review(
            draft=draft.content,
            document_type=document_type,
        )

        # Step 6: Return results without modifying project files.
        return {
            "changes": change_report,
            "classification": classification_report,
            "context_summary": context.get("summary", {}),
            "draft": draft,
            "review": review,
            "requires_human_approval": True,
            "written_to_disk": False,
        }
