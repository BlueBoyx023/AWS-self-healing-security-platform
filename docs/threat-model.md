
# Threat Model — AWS Self-Healing Security Platform

## 1. Objective

Identify threats that could compromise the security detection and automated remediation workflow.

## 2. Assets to Protect

- AWS resources and configurations
- Lambda execution role
- Security event payloads
- Remediation policies
- Audit records
- AWS credentials and permissions

## 3. Trust Boundaries

- AWS Config to EventBridge
- EventBridge to Lambda
- Lambda to AWS APIs
- Lambda to audit storage
- Human approval to remediation execution

## 4. Threat Scenarios

| Threat | Potential Impact | Proposed Mitigation |
|---|---|---|
| Forged security event | Unauthorized remediation | Validate event source and structure |
| Excessive IAM permissions | Privilege escalation | Least-privilege IAM |
| Duplicate event delivery | Repeated actions | Idempotent processing |
| Malicious bucket identifier | Unauthorized resource changes | Resource allowlist |
| Audit log tampering | Loss of evidence | Restrict write and delete permissions |
| Remediation failure | Security exposure remains | Error handling and verification |
| Accidental production changes | Service disruption | Isolated lab and approval controls |

## 5. Security Controls

- Validate every incoming event.
- Restrict remediation to approved resources.
- Separate detection and remediation permissions.
- Log every remediation attempt.
- Verify the resource after remediation.
- Require approval for high-impact actions.

## 6. Initial Scope

The first MVP focuses on detecting and remediating unintended public access to an isolated S3 test bucket.

## 7. Status

Initial threat model — proposed controls have not yet been implemented or tested.
