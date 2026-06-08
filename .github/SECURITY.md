# Security Policy

## Scope

PulseBase ist eine selbst gehostete Gesundheits-App.
ASVS-Level: L2 (Gesundheitsdaten nach Art. 9 DSGVO, Epilepsie-Modus).

## Security-Scanning im SDLC

| Schicht | Tool | Trigger |
|---------|------|---------|
| Secret-Scan | gitleaks | Pre-commit + CI |
| Secret-Baseline | detect-secrets | Pre-commit |
| SAST (Python) | bandit 1.8.3 | Pre-commit + CI |
| SAST (Cross-file) | semgrep 1.164.0 | Pre-commit + CI |
| SCA (Python) | pip-audit 2.8.0 | CI |
| Image-Scan | trivy (CRITICAL+HIGH) | CI |
| JS Lint/Security | Biome | Pre-commit + CI |

## GitHub-natives Secret Scanning

GitHub Advanced Security (Secret Scanning, Code Scanning) ist auf dem Free-Plan für
private Repositories nicht verfügbar (dokumentierte Ausnahme CICD-L4).

Ersatz: gitleaks (Pre-commit + CI) + detect-secrets (Pre-commit-Baseline).

## Sicherheitslücken melden

Schwachstellen bitte **nicht** als öffentliches GitHub Issue melden.
Stattdessen: GitHub → Security → "Report a vulnerability" (Private Disclosure) oder direkt an den Repository-Owner.
Kein Bug-Bounty-Programm; Meldungen werden zeitnah beantwortet.

Für alle anderen Security-Entscheidungen und den aktuellen Sicherheitsstatus:
→ [`docs/security.md`](../docs/security.md)
→ [`docs/review-open-items.md`](../docs/review-open-items.md)
