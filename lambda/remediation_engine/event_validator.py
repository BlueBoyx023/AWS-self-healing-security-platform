

from typing import Any


TRUSTED_EVENT_SOURCE = "aws.config"
EXPECTED_EVENT_TYPE = "Config Rules Compliance Change"
SUPPORTED_RESOURCE_TYPE = "AWS::S3::Bucket"


def validate_event(event: dict[str, Any]) -> dict[str, str]:
    """
    Validate an AWS Config compliance event
    before passing it to the remediation engine.

    Reject malformed, incomplete, or unauthorized events.
    """

    # 1. Validate event structure
    if not isinstance(event, dict):
        raise ValueError("Event must be a dictionary")

    # 2. Validate event ID
    event_id = event.get("id")

    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("Missing or invalid event ID")

    # 3. Validate trusted event source
    if event.get("source") != TRUSTED_EVENT_SOURCE:
        raise ValueError("Untrusted event source")

    # 4. Validate event type
    if event.get("detail-type") != EXPECTED_EVENT_TYPE:
        raise ValueError("Unsupported event type")

    # 5. Validate AWS region
    region = event.get("region")

    if not isinstance(region, str) or not region.strip():
        raise ValueError("Missing or invalid AWS region")

    # 6. Validate event details
    detail = event.get("detail")

    if not isinstance(detail, dict):
        raise ValueError("Missing event details")

    # 7. Validate compliance evaluation
    evaluation = detail.get("newEvaluationResult")

    if not isinstance(evaluation, dict):
        raise ValueError("Missing compliance evaluation")

    if evaluation.get("complianceType") != "NON_COMPLIANT":
        raise ValueError("Resource is not non-compliant")

    # 8. Validate resource identifier
    identifier = evaluation.get("evaluationResultIdentifier")

    if not isinstance(identifier, dict):
        raise ValueError("Missing resource identifier")

    qualifier = identifier.get("evaluationResultQualifier")

    if not isinstance(qualifier, dict):
        raise ValueError("Missing resource qualifier")

    # 9. Validate supported resource type
    resource_type = qualifier.get("resourceType")

    if resource_type != SUPPORTED_RESOURCE_TYPE:
        raise ValueError("Unsupported resource type")

    # 10. Validate bucket identifier
    bucket_name = qualifier.get("resourceId")

    if not isinstance(bucket_name, str) or not bucket_name.strip():
        raise ValueError("Missing or invalid bucket identifier")

    # 11. Return validated event data
    return {
        "event_id": event_id,
        "region": region,
        "bucket_name": bucket_name,
        "resource_type": resource_type,
        "compliance_status": "NON_COMPLIANT",
        "rule_name": str(detail.get("configRuleName", "")),
    }
