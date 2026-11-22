
# Security Testing

## Purpose

This directory contains automated tests for the AWS Self-Healing Security Platform, its documentation tools, and DevDoc.

## Implemented AWS Test Coverage

### 1. S3 Public Access Detection
Verify that unintended public access is detected.

### 2. Approved Remediation
Verify that the remediation engine executes an approved corrective action.

### 3. Unauthorized Remediation
Verify that unapproved actions are rejected.

### 4. Duplicate Event Handling
Verify that duplicate security events do not cause harmful repeated actions.

### 5. Remediation Failure
Verify that errors are handled and recorded correctly.

### 6. Post-Remediation Verification
Verify that the resource reaches the intended secure configuration.

## DevDoc and Documentation Tool Coverage

- Change analysis, classification, and context construction.
- Secret filtering and outbound AI request rejection.
- OpenAI adapter request mapping, sanitized errors, response validation, and size limits using mocked API clients.
- Documentation draft review without automatic file writes.
- Documentation inventory, project-status, and test-report validation.

See `tests/devdoc/` and `tests/test_documentation_tools.py` for the current test modules.

## Testing Principles

- Test in an isolated AWS environment.
- Never use production resources.
- Include positive and negative tests.
- Record actual execution evidence.
- Do not claim a test passed before execution.

## Development Status

Local unit tests are implemented and use mocked AWS and AI API clients. The latest full run on 22 November 2026 passed 282 tests and 9 subtests, with 0 skipped. This does not establish live AWS deployment or integration.
