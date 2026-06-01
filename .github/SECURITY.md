# Security Policy

## Scope

PulseBase ist ein selbst gehostetes Homelab-Projekt ohne öffentliche Benutzer.
ASVS-Level: L2 (Gesundheitsdaten, DSGVO, Epilepsie-Modus).

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

Da PulseBase ein privates Homelab-Projekt ist, gibt es kein öffentliches
Bug-Bounty-Programm. Schwachstellen direkt an den Repository-Owner melden.

Für alle anderen Security-Entscheidungen und den aktuellen Sicherheitsstatus:
→ [`docs/security.md`](../docs/security.md)
→ [`docs/app-eval-report.md`](../docs/app-eval-report.md)
