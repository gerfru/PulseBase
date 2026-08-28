# ADR-0006: Operator-initiated artifact promotion on the Mac mini

## Status

Accepted — 2026-08-28

Related: [Architecture concept](0006-architecture-concept.md)

Partially supersedes [ADR-0002](0002-cd-pipeline.md): automatic push deployment remains
deferred, but building application images on the production host is no longer the target.

## Context

PulseBase runs as a Docker Compose stack on one local Apple Silicon Mac mini. Pull-request
CI already tests and scans the application, and Release Please creates version tags and
GitHub releases. Production still builds mutable source checkouts with `make up`; no
published application artifact or bounded rollback target exists.

Giving GitHub SSH or Docker access to the production host would add unnecessary privilege.
A single-host system also gains no availability from Kubernetes, rolling updates, or a
self-hosted Actions runner on that same host.

## Decision

GitHub-hosted release CI builds the first-party images once for `linux/amd64` and
`linux/arm64`, then publishes them to GHCR by immutable manifest digest:

- API
- sync-service
- ml-service
- backup
- Flyway migrations containing the versioned SQL files

Every release publishes a schema-versioned JSON manifest containing the release version,
Git commit and exact image references. CI scans the published images, creates per-image
SBOMs and provenance attestations, and signs images and the release manifest keylessly via
GitHub OIDC and Sigstore Cosign.

Production deployment remains an explicit local operator action:

```text
make deploy RELEASE=vX.Y.Z
```

The deploy command verifies the signed manifest, pulls all image digests before mutation,
checks backup freshness, creates an encrypted pre-deployment backup, runs forward-only
migrations, and applies the image-only Compose model with `up -d --wait`. It probes API
readiness inside the host boundary and separately checks the client-facing route. On an
application health failure it reapplies the previous image manifest. It never attempts an
automatic database rollback.

The current source-build Compose path remains available for development. Production uses a
separate Compose file with no `build:` directives and no migration bind mount.

## Security Boundaries

- GitHub receives no SSH key, inbound route, production secret, or Docker socket access.
- The Mac mini is not registered as a general GitHub Actions self-hosted runner.
- Production secrets remain in owner-readable local environment files.
- GHCR authentication, when package visibility requires it, uses a read-only credential in
  the Docker credential helper rather than a project environment file.
- Downloaded manifests are parsed as data and are never sourced as shell code.
- Signature verification pins the repository workflow identity and GitHub OIDC issuer.

## Database Compatibility

All schema changes use Expand/Contract across releases. An application rollback must remain
compatible with the already-applied migration. Destructive contract migrations occur only
after the rollback window for the expanded schema has closed.

## Consequences

Positive:

- Production runs the same immutable, scanned artifact produced by release CI.
- ARM64 is an explicit release platform.
- Rollback selects known image digests rather than rebuilding historical source.
- Deploy approval and production credentials remain local.
- Deployment receipts provide a measurable DORA baseline.

Accepted limitations:

- Deployments are continuous delivery, not automatic continuous deployment.
- Recreating a single instance can cause brief supervised interruption.
- The Mac mini, Docker runtime, storage, power and network remain single points of failure.
- Application rollback cannot reverse an incompatible database migration.

## Rejected Alternatives

- GitHub Actions SSH deployment: unnecessary production credential and network exposure.
- Production self-hosted runner: workflow code would gain production and Docker control.
- Watchtower or unattended tag polling: no explicit approval or bounded health rollback.
- Kubernetes on one host: additional control-plane complexity without host redundancy.
- Mutable tags such as `latest`: deployment identity is always an image digest.

## Revisit Triggers

Reassess this decision if production moves off the Mac mini, requires contractual
availability, adds another host, needs zero-downtime traffic switching, or gains multiple
operators/environments that justify a persistent staging environment and automated
promotion approvals.
