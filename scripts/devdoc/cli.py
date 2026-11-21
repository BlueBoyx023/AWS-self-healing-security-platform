

"""Command-line interface for DevDoc."""

import argparse
import sys

from scripts.devdoc.openai_provider import (
    DEFAULT_MAX_CONTEXT_BYTES,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SECONDS,
    OpenAIProvider,
)
from scripts.devdoc.orchestrator import DevDocOrchestrator


def create_parser():
    """Create the DevDoc command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="devdoc",
        description="Generate reviewable project documentation drafts.",
    )

    parser.add_argument(
        "--repo",
        default=".",
        help="Path to the Git repository. Defaults to the current directory.",
    )

    parser.add_argument(
        "--baseline",
        default="HEAD",
        help="Git baseline used for change analysis. Defaults to HEAD.",
    )

    parser.add_argument(
        "--document-type",
        default="technical documentation",
        help="Documentation type to generate.",
    )

    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=100_000,
        help="Maximum size of an individual context file.",
    )

    parser.add_argument(
        "--max-total-bytes",
        type=int,
        default=1_000_000,
        help="Maximum total context size.",
    )

    parser.add_argument(
        "--model",
        default=None,
        help="OpenAI model; defaults to DEVDOC_OPENAI_MODEL or the adapter default.",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="OpenAI request timeout in seconds.",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Maximum SDK retries (0 to 5).",
    )

    parser.add_argument(
        "--max-context-bytes",
        type=int,
        default=DEFAULT_MAX_CONTEXT_BYTES,
        help="Maximum serialized context size sent to OpenAI.",
    )

    return parser


def main(argv=None, provider=None):
    """Run DevDoc and print a draft for human review.

    The provider is injected so that the CLI remains independent
    of any specific AI service.
    """

    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        if provider is None:
            provider = OpenAIProvider(
                model=args.model,
                timeout=args.timeout,
                max_retries=args.max_retries,
                max_context_bytes=args.max_context_bytes,
            )

        orchestrator = DevDocOrchestrator(
            repo_path=args.repo,
            ai_provider=provider,
            baseline=args.baseline,
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
        )

        result = orchestrator.run(
            document_type=args.document_type
        )

        print("\n=== DEVDOC GENERATION RESULT ===")
        print(f"Repository: {args.repo}")
        print(f"Baseline: {args.baseline}")
        print(f"Document type: {args.document_type}")

        print("\n=== CONTEXT SUMMARY ===")
        for key, value in result["context_summary"].items():
            print(f"{key}: {value}")

        print("\n=== GENERATED DOCUMENTATION DRAFT ===")
        print(result["draft"].content)

        print("\n=== DOCUMENTATION REVIEW ===")
        review = result["review"]

        print(f"Structural checks passed: {review.approved}")

        for issue in review.issues:
            print(f"ISSUE: {issue}")

        for warning in review.warnings:
            print(f"WARNING: {warning}")

        print("\n=== PUBLICATION STATUS ===")
        print("Human approval required: Yes")
        print("Written to disk: No")

        return 0

    except Exception as error:
        print(f"DevDoc error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
