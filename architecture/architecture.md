# System Architecture

## Project
AWS Self-Healing Security Platform

## Purpose
Document the architecture, components, and security event flow.

## Initial Architecture Components

- AWS Config — Configuration compliance detection
- Amazon EventBridge — Event routing
- AWS Lambda — Remediation engine
- AWS IAM — Permissions and access control
- Amazon S3 — Audit evidence storage
- Amazon CloudWatch — Logging and monitoring

## Initial Security Scenario

Detect unintended public access to an S3 bucket and execute an approved remediation workflow.

## Architecture Status

Initial design — implementation pending.
