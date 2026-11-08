# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅        |

## Reporting a Vulnerability

Please report security vulnerabilities privately:

1. **Email:** [SECURITY_CONTACT] (replace with actual contact)
2. **GitHub:** Use [Security Advisories](../../security/advisories) tab

## What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment:** within 48 hours
- **Fix target:** within 2 weeks for critical, 30 days for medium/low
- **Disclosure:** coordinated with reporter

## Security Features

- PII redaction (Presidio + regex for RU)
- Provider allowlist (Russian providers by default)
- Foreign provider double opt-in (152-FZ compliance)
- OTel redaction middleware
- Audit logging without PII values
- Hash-chain annotations (tamper detection)
