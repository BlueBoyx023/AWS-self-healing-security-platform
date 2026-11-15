
"""
AWS Self-Healing Security Platform
Centralized Security Orchestrator

Coordinates:
1. Security event validation
2. Remediation policy evaluation
3. Automated S3 remediation
4. Post-remediation verification
5. Structured audit logging
6. CloudWatch security metrics

Dry-run mode is enabled by default.
"""

from typing import Any

from event_validator import validate_event
from policy_engine import is_remediation_allowed
from remediation_engine import remediate_s3_bucket
from verification_engine import verify_s3_bucket

from audit_logger import write_audit_record
from metrics import record_security_event

from error_handler import (
    ValidationError,
    AuthorizationError,
    RemediationExecutionError,
    VerificationError,
    handle_error,
)


def _record_metric_safely(
    cloudwatch_client: Any,
    event_type: str,
    bucket_name: str = "unknown",
    environment: str = "development",
) -> bool:
    """Publish CloudWatch metrics without interrupting security controls."""

    if cloudwatch_client is None:
        return False

    try:
        return record_security_event(
            cloudwatch_client=cloudwatch_client,
            event_type=event_type,
            bucket_name=bucket_name,
            environment=environment,
        )
    except Exception:
        return False


def _write_audit_record(
    event_id: str,
    event_type: str,
    resource_type: str,
    resource_id: str,
    action: str,
    status: str,
    verification_status: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Persist a structured audit record.

    Audit persistence failures are propagated to the caller.
    """

    return write_audit_record(
        event_id=event_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        status=status,
        verification_status=verification_status,
        error=error,
    )


def _build_error_response(
    error: Exception,
    status: str,
    stage: str,
    bucket_name: str | None = None,
    **extra: Any,
) -> dict[str, Any]:

    response = handle_error(error)

    response["status"] = status
    response["stage"] = stage

    if bucket_name is not None:
        response["bucket_name"] = bucket_name

    response.update(extra)

    return response


def process_security_event(
    event: dict[str, Any],
    allowed_buckets: set[str],
    s3_client: Any,
    dry_run: bool = True,
    cloudwatch_client: Any = None,
    environment: str = "development",
) -> dict[str, Any]:
    """
    Execute the complete AWS security remediation workflow.

    Audit logging is mandatory for workflow outcomes.
    CloudWatch metrics are optional and fail safely.
    """

    event_id = (
        str(event.get("id", "unknown"))
        if isinstance(event, dict)
        else "unknown"
    )

    bucket_name = "unknown"
    resource_type = "AWS::S3::Bucket"
    action = "BLOCK_PUBLIC_ACCESS"
    event_type = "SECURITY_FINDING"

    # STEP 1: Validate incoming security event
    try:
        validated_event = validate_event(event)

        event_id = str(validated_event.get("event_id") or event_id)
        bucket_name = validated_event["bucket_name"]
        resource_type = validated_event["resource_type"]

    except (ValueError, TypeError) as error:
        validation_error = ValidationError(str(error))

        response = _build_error_response(
            error=validation_error,
            status="REJECTED",
            stage="VALIDATION",
        )

        _write_audit_record(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=bucket_name,
            action=action,
            status="REJECTED",
            error=str(error),
        )

        return response

    except Exception as error:
        response = _build_error_response(
            error=error,
            status="FAILED",
            stage="VALIDATION",
        )

        _write_audit_record(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=bucket_name,
            action=action,
            status="FAILED",
            error="Unexpected validation failure",
        )

        return response

    # STEP 2: Evaluate remediation authorization
    try:
        authorized = is_remediation_allowed(
            resource_type=resource_type,
            bucket_name=bucket_name,
            allowed_buckets=allowed_buckets,
        )

    except Exception as error:
        _record_metric_safely(
            cloudwatch_client,
            "failure",
            bucket_name,
            environment,
        )

        response = _build_error_response(
            error=error,
            status="FAILED",
            stage="POLICY",
            bucket_name=bucket_name,
        )

        _write_audit_record(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=bucket_name,
            action=action,
            status="FAILED",
            error="Policy evaluation failed",
        )

        return response

    if not authorized:
        _record_metric_safely(
            cloudwatch_client,
            "unauthorized",
            bucket_name,
            environment,
        )

        authorization_error = AuthorizationError(
            "Resource is not authorized for remediation.",
            details={
                "resource_type": resource_type,
                "bucket_name": bucket_name,
            },
        )

        response = _build_error_response(
            error=authorization_error,
            status="DENIED",
            stage="POLICY",
            bucket_name=bucket_name,
        )

        _write_audit_record(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=bucket_name,
            action=action,
            status="DENIED",
            error="Resource not authorized",
        )

        return response

    # STEP 3: Execute S3 remediation
    try:
        remediation_result = remediate_s3_bucket(
            bucket_name=bucket_name,
            s3_client=s3_client,
            dry_run=dry_run,
        )

    except Exception:
        _record_metric_safely(
            cloudwatch_client,
            "failure",
            bucket_name,
            environment,
        )

        remediation_error = RemediationExecutionError(
            "S3 remediation execution failed.",
            details={
                "bucket_name": bucket_name,
            },
        )

        response = _build_error_response(
            error=remediation_error,
            status="FAILED",
            stage="REMEDIATION",
            bucket_name=bucket_name,
        )

        _write_audit_record(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=bucket_name,
            action=action,
            status="FAILED",
            error="Remediation execution failed",
        )

        return response

    if remediation_result.get("status") not in ("SUCCESS", "DRY_RUN"):
        _record_metric_safely(
            cloudwatch_client,
            "failure",
            bucket_name,
            environment,
        )

        remediation_error = RemediationExecutionError(
            "Remediation operation did not complete successfully.",
            details={
                "bucket_name": bucket_name,
                "remediation_status": remediation_result.get("status"),
            },
        )

        response = _build_error_response(
            error=remediation_error,
            status="FAILED",
            stage="REMEDIATION",
            bucket_name=bucket_name,
            remediation=remediation_result,
        )

        _write_audit_record(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=bucket_name,
            action=action,
            status="FAILED",
            error="Remediation returned failure",
        )

        return response

    # STEP 4: Handle dry-run execution
    if dry_run:
        _record_metric_safely(
            cloudwatch_client,
            "dry_run",
            bucket_name,
            environment,
        )

        _write_audit_record(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=bucket_name,
            action=action,
            status="DRY_RUN",
            verification_status="SKIPPED",
        )

        return {
            "status": "SIMULATED",
            "bucket_name": bucket_name,
            "remediation": remediation_result,
            "verification": "SKIPPED",
        }

    # STEP 5: Verify resulting S3 configuration
    try:
        verification_result = verify_s3_bucket(
            bucket_name=bucket_name,
            s3_client=s3_client,
        )

    except Exception:
        _record_metric_safely(
            cloudwatch_client,
            "verification_failure",
            bucket_name,
            environment,
        )

        verification_error = VerificationError(
            "Post-remediation verification failed.",
            details={
                "bucket_name": bucket_name,
            },
        )

        response = _build_error_response(
            error=verification_error,
            status="FAILED",
            stage="VERIFICATION",
            bucket_name=bucket_name,
            remediation=remediation_result,
        )

        _write_audit_record(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=bucket_name,
            action=action,
            status="FAILED",
            verification_status="UNVERIFIED",
            error="Verification execution failed",
        )

        return response

    # STEP 6: Record verification outcome
    verification_status = verification_result.get("status")

    if verification_status in ("SUCCESS", "VERIFIED"):
        final_status = verification_status
        audit_status = verification_status

        _record_metric_safely(
            cloudwatch_client,
            "success",
            bucket_name,
            environment,
        )

    else:
        final_status = "UNVERIFIED"
        audit_status = "UNVERIFIED"

        _record_metric_safely(
            cloudwatch_client,
            "verification_failure",
            bucket_name,
            environment,
        )

    # STEP 7: Persist final audit record
    _write_audit_record(
        event_id=event_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=bucket_name,
        action=action,
        status=audit_status,
        verification_status=verification_status,
    )

    # STEP 8: Return final workflow outcome
    return {
        "status": final_status,
        "bucket_name": bucket_name,
        "remediation": remediation_result,
        "verification": verification_result,
    }
