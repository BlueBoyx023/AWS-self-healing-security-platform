

"""
AWS Self-Healing Security Platform
Module: Verification Engine

Purpose:
Verify that S3 Block Public Access settings
were successfully applied after remediation.
"""


EXPECTED_SETTINGS = {
    "BlockPublicAcls": True,
    "IgnorePublicAcls": True,
    "BlockPublicPolicy": True,
    "RestrictPublicBuckets": True
}


def verify_s3_bucket(bucket_name: str, s3_client) -> dict:
    """
    Retrieve and verify all four S3 Block Public
    Access settings.
    """

    if not isinstance(bucket_name, str) or not bucket_name.strip():
        raise ValueError("Invalid bucket name")

    if s3_client is None:
        raise ValueError("S3 client is required")

    try:
        response = s3_client.get_public_access_block(
            Bucket=bucket_name
        )

        actual_settings = response.get(
            "PublicAccessBlockConfiguration"
        )

        if not isinstance(actual_settings, dict):
            return {
                "status": "UNVERIFIED",
                "bucket_name": bucket_name,
                "message": "Missing public access configuration."
            }

        failed_settings = [
            setting
            for setting, expected in EXPECTED_SETTINGS.items()
            if actual_settings.get(setting) is not expected
        ]

        if failed_settings:
            return {
                "status": "UNVERIFIED",
                "bucket_name": bucket_name,
                "message": "Security settings do not match.",
                "failed_settings": failed_settings
            }

        return {
            "status": "VERIFIED",
            "bucket_name": bucket_name,
            "message": "All four security settings verified."
        }

    except Exception as error:
        return {
            "status": "UNVERIFIED",
            "bucket_name": bucket_name,
            "message": str(error)
        }
