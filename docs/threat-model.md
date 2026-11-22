# Threat Model — AWS Self-Healing Security Platform

## 1. Objective

Identify threats that could compromise the security detection, authorization, remediation, and audit workflow.

This threat model distinguishes implemented application controls from planned production security controls.

## 2. Assets to Protect

- AWS resources and configurations.
- AWS Lambda execution role and permissions.
- Security event payloads.
- Remediation policies and resource allowlists.
- Audit records.
- AWS credentials and permissions.
- Event-processing and idempotency state.

## 3. Trust Boundaries

- AWS Config to EventBridge.
- EventBridge to the remediation application.
- Application to AWS service APIs.
- Application to audit storage.
- Application authorization policy to remediation execution.
- Human approval to high-impact remediation (planned).

The current implementation is locally tested with mocked AWS interactions. These trust boundaries require validation in a deployed AWS environment.

## 4. Threat Scenarios and Mitigations

| Threat | Potential Impact | Current Mitigation | Status |
|---|---|---|---|
| Forged or malformed security event | Unauthorized or incorrect processing | Event source, event type, structure, and required-field validation | Implemented and unit tested |
| Excessive IAM permissions | Privilege escalation or unauthorized AWS operations | Least-privilege execution role and scoped permissions | Planned |
| Duplicate event delivery | Repeated remediation attempts | Event ID tracking, leases, ownership tokens, and duplicate rejection | Implemented locally and unit tested |
| Malicious bucket identifier | Unauthorized resource modification | S3 resource-type validation and application allowlist | Implemented and unit tested |
| Audit log tampering | Loss or alteration of investigation evidence | Structured local audit logging | Logging implemented; tamper-resistant storage planned |
| Remediation API failure | Public exposure remains unresolved | Centralized error handling and failure recording | Implemented and unit tested |
| Verification failure | Incorrectly reporting remediation as successful | Independent verification of all four S3 Block Public Access settings | Implemented and unit tested |
| Accidental production changes | Service disruption or unintended configuration changes | Dry-run enabled by default | Implemented; approval workflow planned |
| Stale event ownership | Concurrent or outdated workers modifying event state | Lease expiration, ownership tokens, and stale-event recovery | Implemented locally and unit tested |
| In-memory state loss | Duplicate processing after process restart | Durable distributed state storage | Planned |

## 5. Implemented Security Controls

### 5.1 Event Validation

- Validate incoming event structure.
- Require a non-empty string event identifier.
- Validate the expected event source and detail type.
- Require a non-compliant evaluation result.
- Restrict processing to S3 bucket resources.
- Reject missing or invalid bucket identifiers.

### 5.2 Application-Level Authorization

- Restrict remediation to approved bucket names.
- Reject unsupported resource types.
- Reject invalid allowlist configurations.
- Deny resources that are not explicitly authorized.

This application-level allowlist does not replace AWS IAM authorization.

### 5.3 Controlled Remediation

- Permit only predefined S3 Block Public Access settings.
- Enable all four Block Public Access controls during live remediation.
- Enable dry-run mode by default.
- Require explicit configuration to execute live remediation.

### 5.4 Idempotency and Event Ownership

- Reject duplicate event claims.
- Use time-limited processing leases.
- Validate ownership tokens before event completion or failure.
- Recover events after lease expiration.
- Prevent previous owners from modifying recovered event records.

The current default implementation uses an in-memory store and does not provide distributed durability.

### 5.5 Audit and Monitoring

- Write structured JSON Lines audit records.
- Record remediation and verification outcomes.
- Publish predefined CloudWatch security metrics when a client is supplied.
- Handle metric publication failures without interrupting remediation.

Audit records currently use local file storage. Immutable centralized audit storage is not implemented.

### 5.6 Verification and Failure Handling

- Retrieve S3 Block Public Access configuration after live remediation.
- Verify all four expected settings.
- Report unsuccessful or incomplete verification as UNVERIFIED.
- Use centralized error response handling.
- Record failure outcomes in the audit workflow.

## 6. Planned Production Security Controls

The following controls require implementation or validation:

- Dedicated least-privilege AWS IAM execution policies.
- Separation of detection and remediation permissions.
- Durable distributed idempotency storage.
- Lease renewal and distributed event coordination.
- Tamper-resistant centralized audit storage.
- Human approval for high-impact remediation.
- Automated escalation and notification.
- Production deployment and operational recovery procedures.
- Live AWS integration testing.

## 7. Initial Scope

The MVP focuses on detecting and remediating unintended public access to approved S3 test buckets.

The application workflow is implemented and locally unit tested. Live AWS deployment and production security controls remain outstanding.

## 8. Testing and Evidence

Local pytest execution was verified on 22 November 2026:

- 282 tests passed.
- 9 subtests passed.
- No test failures or skipped tests were reported.
- Unit tests use mocked AWS service clients.
- All eight documented functional test scenarios have matching test coverage.

The earlier 91-test screenshot is historical evidence. Current machine-readable results are recorded in `documentation/test_results.json`. These results establish local application test coverage, not live AWS integration or production IAM validation.

## 9. Residual Risks

- In-memory event state can be lost when the process restarts.
- Concurrent Lambda environments are not coordinated by the default store.
- A fixed processing lease may expire during a long-running operation.
- Local audit files do not provide immutable evidence.
- AWS IAM permissions have not been implemented and validated in project policies.
- No human approval workflow currently gates high-impact remediation.
- Live AWS service behavior has not yet been validated.

## 10. Threat Model Status

Core application-level mitigations are implemented and locally unit tested.

Production IAM enforcement, durable distributed processing, tamper-resistant audit storage, human approval, and live AWS validation remain planned.
