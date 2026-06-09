#!/bin/sh
# Backup sidecar entrypoint.
#  - With args:  exec them   (one-off, e.g. `docker compose run --rm backup /scripts/backup.sh`)
#  - No args:    run the daily backup scheduler loop (long-running service mode)
#
# Non-root, no cron daemon: a simple wall-clock poll fires backup.sh once per day at
# BACKUP_HOUR:BACKUP_MINUTE (UTC). Avoids per-arch cron binaries and root requirements.
set -eu

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

: "${BACKUP_HOUR:=3}"
: "${BACKUP_MINUTE:=30}"
target=$(printf '%02d:%02d' "$BACKUP_HOUR" "$BACKUP_MINUTE")

log() { printf '{"ts":"%s","svc":"backup","level":"info","msg":"%s"}\n' "$(date -u +%FT%TZ)" "$1"; }
log "scheduler.start daily_at_utc=$target"

last=""
while true; do
  now=$(date -u +%H:%M)
  today=$(date -u +%F)
  if [ "$now" = "$target" ] && [ "$last" != "$today" ]; then
    last="$today"
    log "scheduler.trigger"
    /scripts/backup.sh || log "scheduler.backup_failed"
  fi
  sleep 30
done
