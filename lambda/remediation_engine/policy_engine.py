

"""
AWS Self-Healing Security Platform
Module: Policy Engine

Purpose:
Authorize or deny remediation based on
explicit security policies and resource allowlists.
"""


SUPPORTED_RESOURCE_TYPE = "AWS::S3::Bucket"


def is_remediation_allowed(
    resource_type: str,
    bucket_name: str,
    allowed_buckets: set[str]
) -> bool:
    """
    Determine whether an S3 bucket is authorized
    for automated security remediation.

    Fail closed: invalid or unauthorized resources
    are always denied.
    """

    # 1. Validate resource type
    if resource_type != SUPPORTED_RESOURCE_TYPE:
        return False

    # 2. Validate bucket identifier
    if not isinstance(bucket_name, str) or not bucket_name.strip():
        return False

    # 3. Validate allowlist
    if not isinstance(allowed_buckets, set):
        return False

    if not all(
        isinstance(name, str) and name.strip()
        for name in allowed_buckets
    ):
        return False

    # 4. Check explicit authorization
    if bucket_name not in allowed_buckets:
        return False

    # 5. Resource is approved
    return True
