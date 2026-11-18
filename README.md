
# AWS Self-Healing Security Platform

**Event-Driven Cloud Security Detection, Automated Remediation & Verification**

[![Python](https://img.shields.io/badge/Python-3.14-blue)](https://www.python.org/)
[![Testing](https://img.shields.io/badge/Tests-91%20Passed-success)](screenshots/README.md)
[![Status](https://img.shields.io/badge/Status-Under%20Development-orange)](#project-status)
[![AWS](https://img.shields.io/badge/Cloud-AWS-orange)](https://aws.amazon.com/)

---

## 1. Project Overview

The AWS Self-Healing Security Platform is an event-driven cloud security automation project designed to detect security misconfigurations, evaluate remediation policies, execute authorized corrective actions, and verify the resulting security posture.

The platform aims to reduce manual security intervention through controlled, policy-driven remediation while maintaining accountability, auditability, and operational safety.

The initial implementation focuses on securing Amazon S3 buckets against unintended public access.

**Development approach:** Local-first implementation using Python, automated tests, and mocked AWS interactions before live AWS integration.

## 2. Project Objectives

- Detect AWS security misconfigurations.
- Validate incoming security events.
- Enforce resource-specific remediation policies.
- Prevent unauthorized remediation.
- Execute approved security remediation.
- Prevent harmful duplicate event processing.
- Verify remediation outcomes.
- Maintain structured audit records.
- Monitor security operations through metrics.
- Support controlled recovery from processing failures.

## 3. System Architecture

### Target AWS Architecture

AWS Config → Amazon EventBridge → AWS Lambda → Policy Evaluation → S3 Remediation → Verification → Audit & Monitoring

### Core Components

| Component | Responsibility |
|---|---|
| AWS Config | Security compliance detection |
| Amazon EventBridge | Security event routing |
| AWS Lambda | Event processing and orchestration |
| AWS IAM | Access control and permissions |
| Amazon S3 | Resource remediation and audit evidence storage |
| Amazon CloudWatch | Monitoring, logs and metrics |
| Python | Security automation and remediation logic |
| Terraform | Infrastructure as Code |

*The above describes the intended AWS deployment architecture. Live AWS integration and deployment are separate milestones.*

## 4. Implemented Components

The following components have been implemented and developed with local automated testing:

| Component | Implementation |
|---|---|
| Event Validator | Validates incoming AWS Config events |
| Policy Engine | Enforces resource allowlists and remediation authorization |
| S3 Remediation Engine | Executes controlled S3 remediation logic |
| Verification Engine | Checks remediation outcomes |
| Centralized Orchestrator | Coordinates the remediation workflow |
| Idempotency Manager | Prevents duplicate event processing |
| Lease-Based Processing | Manages event ownership and stale-event recovery |
| Audit Logger | Generates structured audit records |
| Metrics Module | Records security operation metrics |
| Error Handler | Centralizes workflow error handling |

## 5. Security Controls

- Fail-closed remediation authorization.
- Explicit resource allowlisting.
- Event source and event-type validation.
- Required-field validation.
- Event identifier validation.
- Rejection of malformed event identifiers.
- Duplicate event protection.
- Lease-based event ownership.
- Dry-run execution enabled by default.
- Post-remediation verification.
- Structured audit logging.
- Centralized error handling.

## 6. Testing & Validation

The platform uses Python unit tests and mocked AWS responses during local development.

### Latest Verified Test Results

| Metric | Result |
|---|---:|
| Tests passed | 91 |
| Subtests passed | 9 |
| Test failures | 0 |
| Test framework | pytest |
| Execution environment | Local Python virtual environment |

### Test Execution Evidence

![Local Test Results](screenshots/test-results-91-passed.png)

See the [Screenshots & Evidence](screenshots/README.md) directory for additional implementation and testing evidence.

**Testing qualification:** These results demonstrate local automated testing. They do not establish live AWS deployment or successful execution against real AWS resources.

## 7. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Security automation |
| pytest | Automated testing |
| AWS Config | Configuration compliance |
| Amazon EventBridge | Event-driven architecture |
| AWS Lambda | Serverless execution |
| Amazon S3 | Storage and remediation target |
| AWS IAM | Identity and access management |
| Amazon CloudWatch | Monitoring and metrics |
| Terraform | Infrastructure as Code |
| Git & GitHub | Version control and project documentation |

## 8. Development Roadmap

- [x] Core repository and project structure
- [x] Event validation
- [x] Remediation policy engine
- [x] S3 remediation logic
- [x] Verification engine
- [x] Centralized orchestration
- [x] Structured audit logging
- [x] Security metrics integration
- [x] Centralized error handling
- [x] Idempotency management
- [x] Lease-based event processing
- [x] Local automated test coverage
- [ ] Additional adversarial security testing
- [ ] Enhanced resource identifier validation
- [ ] Security documentation and threat model validation
- [ ] AWS infrastructure implementation
- [ ] Isolated AWS integration testing
- [ ] Terraform deployment
- [ ] End-to-end AWS remediation testing

## 9. Project Safety & Deployment

The current development environment prioritizes local testing and mocked AWS interactions.

Before live deployment:

- Use isolated AWS test resources.
- Apply least-privilege IAM permissions.
- Review all remediation permissions.
- Keep production resources outside the remediation allowlist.
- Review AWS costs before deployment.
- Verify remediation behavior before enabling automated actions.
- Never commit AWS credentials, access keys, or secrets.
- Document resource cleanup procedures.

Live AWS remediation is not claimed by the current local test results.

## 10. Repository Structure

```text
AWS-self-healing-security-platform/
│
├── architecture/
├── docs/
├── lambda/
│   └── remediation_engine/
│       ├── audit_logger.py
│       ├── error_handler.py
│       ├── event_validator.py
│       ├── idempotency.py
│       ├── metrics.py
│       ├── orchestrator.py
│       ├── policy_engine.py
│       ├── remediation_engine.py
│       └── verification_engine.py
│
├── policies/
├── screenshots/
├── terraform/
├── tests/
│
├── PROJECT_STATUS.md
├── README.md
└── LICENSE
```

## 11. Disclaimer

This is an educational cloud security engineering project.

All testing and deployment must be performed in AWS accounts and environments owned by the developer or explicitly authorized for assessment.

---

**Author:** BlueBoyx023

**Project Focus:** AWS Security Engineering | Cloud Security Automation | Security Remediation | Autonomous Cloud Defense