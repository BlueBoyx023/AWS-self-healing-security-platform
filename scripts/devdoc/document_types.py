"""Supported document types shared across the DevDoc workflow."""

DOCUMENT_TYPES = (
    "technical documentation",
    "security documentation",
    "architecture documentation",
)


def validate_document_type(document_type: str) -> str:
    """Return a canonical document type or reject unsupported labels."""

    if not isinstance(document_type, str):
        raise ValueError("Unsupported document type.")

    normalized = document_type.strip().lower()
    if normalized not in DOCUMENT_TYPES:
        raise ValueError(
            "Unsupported document type. Choose one of: "
            + ", ".join(DOCUMENT_TYPES)
            + "."
        )
    return normalized
