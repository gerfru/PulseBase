# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.x     | ✅        |
| < 1.0   | ❌        |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Report vulnerabilities privately via [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) (Security → Report a vulnerability).

**Include:**
- Description and potential impact
- Steps to reproduce
- Affected version(s)

**Response time:** I aim to acknowledge reports within 7 days and publish a fix within 30 days for confirmed vulnerabilities.

## Security Design

PulseBase is designed as a self-hosted personal health data application. Key security properties:

- All health data stays on your server — no third-party data sharing
- Passwords hashed with bcrypt (rounds=12)
- CSRF protection on all state-changing routes
- SQL injection prevented via parameterized queries (asyncpg)
- CSP with per-request nonces (`'strict-dynamic'`)
- Session cookies: `httpOnly`, `secure`, `SameSite=Strict`
- Garmin credentials never stored — Fernet-encrypted login tokens only
- Account lockout after 5 failed login attempts
- Full audit log for GDPR consent (Art. 5(2))

## Scope

In scope: authentication, session management, data access controls, injection vulnerabilities, GDPR compliance issues.

Out of scope: denial-of-service attacks on self-hosted instances, issues requiring physical access to the server.
