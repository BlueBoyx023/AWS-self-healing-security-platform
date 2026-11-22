# Remediation Engine

## Purpose

This directory contains the Python application modules for the AWS security remediation workflow. The code is implemented and tested locally; it has not been deployed as an AWS Lambda function.

## Responsibilities

- Receive validated security events.
- Identify the affected AWS resource.
- Evaluate remediation policies.
- Execute approved corrective actions.
- Handle errors and duplicate events.
- Record remediation results.

## Initial Use Case

Remediate unintended public access to an S3 bucket in an isolated test environment.

## Development Status

Application modules and mocked unit tests are implemented. AWS Lambda packaging, least-privilege execution-role policy, deployment, and live integration remain pending.
