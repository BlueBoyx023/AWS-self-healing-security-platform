

"""Generate documentation drafts through the configured AI provider."""

from scripts.devdoc.ai_provider import (
    AIProvider,
    AIRequest,
    AIResponse,
)


class DraftGenerator:
    """Prepare documentation requests and generate reviewable drafts."""

    def __init__(self, provider: AIProvider):
        if not isinstance(provider, AIProvider):
            raise TypeError("provider must implement the AIProvider interface.")

        self.provider = provider

    def generate_draft(
        self,
        context: dict,
        document_type: str = "technical documentation",
    ) -> AIResponse:
        """Generate a documentation draft without writing any files."""

        if not isinstance(context, dict):
            raise ValueError("Context must be a dictionary.")

        if not context:
            raise ValueError("Context cannot be empty.")

        if not isinstance(document_type, str) or not document_type.strip():
            raise ValueError("Document type must be a non-empty string.")

        instruction = f"""
You are a technical documentation assistant for a cloud security project.

Generate a draft for: {document_type}

Requirements:
1. Use only information supported by the supplied project context.
2. Do not invent implementation details, test results, or security controls.
3. Preserve technical terminology, filenames, and component names.
4. Clearly identify missing information instead of guessing.
5. Use clear Markdown headings and structured explanations.
6. Do not modify files or claim that documentation has been saved.
7. Return only the documentation draft.

The draft must be suitable for human review before publication.
""".strip()

        request = AIRequest(
            instruction=instruction,
            context=context,
        )

        response = self.provider.generate(request)

        if not isinstance(response, AIResponse):
            raise TypeError("AI provider must return an AIResponse.")

        return response
