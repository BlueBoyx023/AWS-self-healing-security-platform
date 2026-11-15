

from typing import Any


TRUSTED_EVENT_SOURCE = "aws.config"
EXPECTED_EVENT_TYPE = "Config Rules Compliance Change"
SUPPORTED_RESOURCE_TYPE = "AWS::S3::Bucket"


def validate_event(event: dict[str, Any]) -> dict[str, str]:
    """
    Validate an AWS Config compliance event
    before passing it to the remediation engine.
    """

    if not isinstance(event, dict):
        raise ValueError("Event must be a dictionary")

    if event.get("source") != TRUSTED_EVENT_SOURCE:
        raise ValueError("Untrusted event source")

    if event.get("detail-type") != EXPECTED_EVENT_TYPE:
        raise ValueError("Unsupported event type")

    region = event.get("region")

    if not isinstance(region, str) or not region.strip():
        raise ValueError("Missing or invalid AWS region")

    detail = event.get("detail")

    if not isinstance(detail, dict):
        raise ValueError("Missing event details")

    evaluation = detail.get("newEvaluationResult")

    if not isinstance(evaluation, dict):
        raise ValueError("Missing compliance evaluation")

    if evaluation.get("complianceType") != "NON_COMPLIANT":
        raise ValueError("Resource is not non-compliant")

    identifier = evaluation.get("evaluationResultIdentifier")

    if not isinstance(identifier, dict):
        raise ValueError("Missing resource identifier")

    qualifier = identifier.get("evaluationResultQualifier")

    if not isinstance(qualifier, dict):
        raise ValueError("Missing resource qualifier")

    resource_type = qualifier.get("resourceType")
    bucket_name = qualifier.get("resourceId")

    if resource_type != SUPPORTED_RESOURCE_TYPE:
        raise ValueError("Unsupported resource type")

    if not isinstance(bucket_name, str) or not bucket_name.strip():
        raise ValueError("Missing or invalid bucket identifier")

    return {
        "event_id": str(event.get("id", "")),
        "region": region,
        "bucket_name": bucket_name,
        "resource_type": resource_type,
        "compliance_status": "NON_COMPLIANT",
        "rule_name": str(detail.get("configRuleName", "")),
    }
