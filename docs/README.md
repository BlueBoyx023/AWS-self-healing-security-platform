
# Security Documentation

## Purpose

This directory contains the AWS platform security design and threat model, DevDoc AI security guidance, and current development checkpoint.

## Documents

- [Threat Model](threat-model.md) — identifies AWS platform assets, threats, attack surfaces, and mitigations.
- [Security Design](security-design.md) — documents AWS platform security controls and architecture decisions.
- [DevDoc AI Security Controls](devdoc-security.md) — describes outbound AI data checks and their limitations.
- [Development Handover Checkpoint](RESUME_CHECKPOINT.md) — records current verified progress and next work.
- [Generated Documentation Inventory](generated/documentation_inventory.md) — lists repository Markdown documents and headings.

Remediation policy and incident workflow documents remain future work.

## Security Considerations

- Least-privilege access
- Event validation
- Secure error handling
- Audit logging
- Human approval for high-impact actions
- Protection against unauthorized remediation

## Development Status

AWS security design and threat-model documents describe implemented local controls and clearly identify production controls that remain pending. DevDoc security documentation describes tested controls and detection limitations. Live AWS deployment and IAM validation remain pending.
