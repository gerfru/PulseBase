# PulseBase backup sidecar: pg_dump (PG16) + age encryption + optional rclone offsite.
# Connects to the db service over the internal network (no docker socket, no extra privilege).
FROM postgres:18-alpine@sha256:96d56f7f57c6aacd1fcb908bc83b345ec5f83231ee486dd66a1baadce274db88

# age   = backup encryption (X25519 / ChaCha20-Poly1305), Alpine community
# rclone = optional offsite copy (3-2-1 rule)
RUN apk upgrade --no-cache && apk add --no-cache age rclone

COPY backup.sh restore.sh entrypoint.sh /scripts/
RUN chmod +x /scripts/*.sh \
    && mkdir -p /backups \
    && chown -R postgres:postgres /backups /scripts

# Run as the image's existing non-root postgres user (uid 70). A fresh named volume
# mounted at /backups inherits this ownership, so backups are writable without root.
USER postgres

# Liveness: the scheduler loop must be alive.
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s \
    CMD pgrep -f entrypoint.sh >/dev/null || exit 1

ENTRYPOINT ["/scripts/entrypoint.sh"]
