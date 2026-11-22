# Security Design — AWS Self-Healing Security Platform

## 1. Design Objective

Provide controlled, authorized, and auditable remediation of unintended public access to approved Amazon S3 buckets.

The platform validates incoming security events, evaluates remediation authorization, applies predefined security controls, verifies the resulting configuration, and records workflow outcomes.

This document covers the AWS remediation application. DevDoc's AI-provider security controls are documented separately in [DevDoc AI Security Controls](devdoc-security.md).

The current implementation is designed for local development and testing. Production deployment controls remain subject to further implementation and validation.

## 2. Identity and Access Management

### Current Implementation

- Application-level resource authorization is enforced through an explicit S3 bucket allowlist.
- Remediation is restricted to the supported resource type `AWS::S3::Bucket`.
- Unsupported resource types and invalid resource identifiers are rejected.

### Planned Production Controls

- Create a dedicated AWS Lambda execution role.
- Apply least-privilege IAM permissions.
- Separate detection permissions from remediation permissions.
- Restrict AWS permissions to approved resources wherever supported.
- Avoid wildcard permissions wherever practical.
- Do not store AWS credentials in source code.

**Status:** Application-level authorization is implemented. AWS IAM execution policies have not yet been implemented or validated.

## 3. Security Event Validation

The event validator checks:

- Event structure and dictionary type.
- Non-empty string event identifier.
- Trusted event source (`aws.config`).
- Expected event detail type.
- Non-empty AWS region field.
- Required nested event details.
- Non-compliant evaluation status.
- Supported resource type.
- Non-empty S3 bucket identifier.

Malformed, unsupported, or non-compliant event payloads are rejected.

**Status:** Implemented and covered by unit tests.

## 4. Remediation Authorization and Controls

The remediation policy engine:

- Restricts remediation to `AWS::S3::Bucket`.
- Requires the bucket to exist in the configured application allowlist.
- Rejects invalid resource identifiers and invalid allowlists.
- Fails closed when authorization requirements are not satisfied.

The S3 remediation engine applies these four Block Public Access settings:

- `BlockPublicAcls = True`
- `IgnorePublicAcls = True`
- `BlockPublicPolicy = True`
- `RestrictPublicBuckets = True`

The remediation engine supports dry-run execution, enabled by default.

When dry-run is disabled, it calls the S3 `PutPublicAccessBlock` API operation.

**Status:** Implemented and tested using mocked AWS clients. Live AWS remediation has not yet been validated.

## 5. Idempotency and Event Ownership

The idempotency module provides:

- Duplicate event detection.
- Event status tracking.
- Time-limited processing leases.
- Unique ownership tokens.
- Ownership validation before completing or failing an event.
- Stale-event recovery after lease expiration.
- Protection against previous owners modifying recovered events.

The orchestrator uses a 60-second processing lease.

### Current Limitations

- The default store uses an in-memory dictionary.
- Thread locking protects local in-process operations only.
- Event state is not durable across process restarts.
- Distributed coordination across Lambda execution environments is not implemented.
- Lease renewal is not implemented in the orchestrator.

**Status:** Implemented and unit tested for local execution. Durable distributed idempotency remains planned.

## 6. Logging and Audit

The audit logger writes structured JSON Lines records containing:

- UTC timestamp.
- Event identifier.
- Event type.
- Resource type and identifier.
- Remediation action.
- Execution status.
- Verification status.
- Error information, when applicable.

The logger creates the required directory and appends records to the local audit file.

The orchestrator treats audit logging as mandatory and writes audit evidence before updating the owned event state.

### Current Limitations

- Audit records are stored locally.
- Immutable or tamper-resistant storage is not implemented.
- Centralized audit storage and production access controls remain planned.
- Sensitive-data redaction has not been independently validated.

**Status:** Structured local audit logging is implemented and unit tested.

## 7. Monitoring and Metrics

The metrics module supports predefined security metrics:

- Remediation success.
- Remediation failure.
- Unauthorized attempts.
- Verification failures.
- Dry-run execution.

Metrics are published through the CloudWatch `PutMetricData` API.

The orchestrator handles metric publication failures safely so that optional monitoring failures do not interrupt the remediation workflow.

**Status:** Implemented and unit tested with mocked CloudWatch clients. Live CloudWatch integration remains unvalidated.

## 8. Failure Handling

The centralized error handler provides structured error responses for:

- Validation errors.
- Authorization errors.
- Remediation execution errors.
- Verification errors.
- Unexpected internal errors.

The orchestrator records workflow failures and prevents failed or unverified remediation from being reported as verified success.

Metric publication failures are handled separately and do not interrupt remediation.

### Current Limitations

- Automatic remediation retries are not implemented by the orchestrator.
- Automated escalation and notification workflows are not implemented.
- Recovery from audit-storage failures requires further operational design.

**Status:** Centralized error handling is implemented and unit tested.

## 9. Post-Remediation Verification

After live remediation, the verification engine retrieves the S3 Block Public Access configuration using `GetPublicAccessBlock`.

It verifies that all four expected settings are enabled.

The workflow reports `VERIFIED` only when all four settings match the expected Boolean values.

Missing configuration, mismatched settings, and API errors result in an `UNVERIFIED` outcome.

Dry-run execution skips post-remediation verification because no AWS configuration changes are made.

**Status:** Implemented and unit tested using mocked S3 responses.

## 10. Dry-Run and Deployment Safety

Dry-run mode is enabled by default.

In dry-run mode:

- No S3 remediation API changes are made.
- The workflow records a simulated execution.
- Verification is skipped.
- The event is marked as completed in the local idempotency store.

Live remediation requires explicitly setting `dry_run=False`.

The current project uses local development and mocked AWS interactions for automated testing. Live AWS integration must be performed separately in an isolated test environment.

## 11. Current Scope

The initial implementation focuses on detecting and remediating unintended public access to approved S3 test buckets.

The platform currently provides application-level event validation, authorization, remediation, verification, event ownership, audit logging, metrics, and error handling.

It does not yet implement a complete production AWS deployment architecture.

## 12. Outstanding Production Requirements

The following controls remain planned or require further validation:

- Dedicated least-privilege AWS IAM execution policies.
- Durable distributed idempotency storage.
- Lease renewal and distributed event coordination.
- Centralized and tamper-resistant audit storage.
- Human approval workflow for high-impact remediation.
- Automated escalation and notification.
- Live AWS integration and deployment validation.
- Production operational monitoring and recovery procedures.

## 13. Testing and Validation

The local pytest suite was executed on 22 November 2026.

- 282 tests passed.
- 9 subtests passed.
- No test failures or skipped tests were reported.
- AWS interactions were tested using mocked clients.
- Live AWS integration and IAM least-privilege validation remain pending.

The earlier 91-test screenshot is historical evidence. The current machine-readable report is `documentation/test_results.json`.

## 14. Implementation Status

Core application modules are implemented and locally unit tested.

Production deployment controls, AWS IAM policy implementation, durable distributed state, and live AWS integration remain outstanding.

This document distinguishes verified application behavior from planned production security requirements.
