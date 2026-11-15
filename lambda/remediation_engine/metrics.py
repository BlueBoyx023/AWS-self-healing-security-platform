

from typing import Any


NAMESPACE = "SelfHealingSecurityPlatform"


METRIC_NAMES = {
    "success": "RemediationSuccess",
    "failure": "RemediationFailure",
    "unauthorized": "UnauthorizedAttempt",
    "verification_failure": "VerificationFailure",
    "dry_run": "DryRunExecution",
}


def publish_metric(
    cloudwatch_client: Any,
    metric_name: str,
    value: float = 1.0,
    bucket_name: str = "unknown",
    environment: str = "development",
) -> bool:
    """
    Publish a custom security metric to Amazon CloudWatch.

    Returns False if publishing fails.
    Monitoring failures must not interrupt security controls.
    """

    if cloudwatch_client is None:
        return False

    if metric_name not in METRIC_NAMES.values():
        raise ValueError("Unsupported metric name")

    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("Metric value must be numeric")

    if value < 0:
        raise ValueError("Metric value cannot be negative")

    if not isinstance(bucket_name, str) or not bucket_name.strip():
        raise ValueError("Invalid bucket name")

    if not isinstance(environment, str) or not environment.strip():
        raise ValueError("Invalid environment")

    try:
        cloudwatch_client.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Value": float(value),
                    "Unit": "Count",
                    "Dimensions": [
                        {
                            "Name": "Environment",
                            "Value": environment,
                        },
                        {
                            "Name": "ResourceType",
                            "Value": "S3",
                        },
                    ],
                }
            ],
        )
        return True

    except Exception:
        return False


def record_security_event(
    cloudwatch_client: Any,
    event_type: str,
    bucket_name: str = "unknown",
    environment: str = "development",
) -> bool:
    """
    Record a predefined security event in CloudWatch.
    """

    if event_type not in METRIC_NAMES:
        raise ValueError("Unsupported security event type")

    metric_name = METRIC_NAMES[event_type]

    return publish_metric(
        cloudwatch_client=cloudwatch_client,
        metric_name=metric_name,
        value=1.0,
        bucket_name=bucket_name,
        environment=environment,
    )
