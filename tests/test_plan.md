# Test Plan — AWS Self-Healing Security Platform

## 1. Testing Objective

Validate that the platform detects security events, rejects unauthorized requests, performs approved remediation, and verifies the resulting configuration.

## 2. Functional Tests

| Test ID | Scenario | Expected Result | Coverage |
|---|---|---|---|
| T01 | Valid S3 security event | Event accepted | Implemented and tested |
| T02 | Invalid event source | Event rejected | Implemented and tested |
| T03 | Missing bucket identifier | Event rejected | Implemented and tested |
| T04 | Bucket not in allowlist | Remediation denied | Implemented and tested |
| T05 | Approved remediation | Action executed | Implemented and tested with mocked AWS client |
| T06 | Duplicate event | No harmful repeated action | Implemented and tested |
| T07 | AWS API failure | Error recorded | Implemented and tested with mocked AWS client |
| T08 | Verification failure | Finding remains unresolved | Implemented and tested with mocked AWS client |

## 3. Security Tests

- Attempt unauthorized remediation.
- Submit malformed event payloads.
- Test unexpected resource identifiers.
- Test duplicate event delivery and concurrent claims.
- Test lease expiration and stale-event recovery.
- Verify remediation authorization through the application-level allowlist.
- Least-privilege AWS IAM validation remains pending.

## 4. Evidence Collection

For each test, record:

- Test ID
- Input
- Expected result
- Actual result
- Pass or fail
- Evidence reference

## 5. Testing Environment

Unit tests use Python pytest and mocked AWS client responses.

Live AWS integration tests will be performed later in an isolated test environment.

## 6. Current Status

Unit test execution verified on 19 November 2026.

- 91 tests passed.
- 9 subtests passed.
- No test failures reported.
- All eight documented functional scenarios have matching test coverage.
- AWS interactions are validated using mocked clients.
- Live AWS integration testing remains pending.
- AWS IAM least-privilege policy implementation and validation remain pending.

Test evidence: Local pytest execution.
