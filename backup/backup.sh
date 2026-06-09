#!/bin/sh
# PulseBase DB backup: pg_dump (custom format) -> age-encrypt -> retention -> optional offsite.
# Connects to the DB over the internal Docker network using libpq env vars — no docker socket.
#
# Env:
#   PGHOST/PGPORT/PGUSER/PGPASSWORD  libpq connection (PGHOST defaults to "db")
#   PGDATABASE                       database to dump (default: garmin)
#   AGE_RECIPIENT                    age PUBLIC key — REQUIRED, encrypts every backup
#   BACKUP_DIR                       output dir (default: /backups)
#   BACKUP_RETENTION_DAYS            delete local backups older than N days (default: 14)
#   RCLONE_REMOTE                    optional offsite target (e.g. b2:pulsebase-backups)
set -eu

: "${PGHOST:=db}"
: "${PGPORT:=5432}"
: "${PGDATABASE:=garmin}"
: "${BACKUP_DIR:=/backups}"
: "${BACKUP_RETENTION_DAYS:=14}"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"
export PGHOST PGPORT PGDATABASE

log() { printf '{"ts":"%s","svc":"backup","level":"%s","msg":"%s"}\n' "$(date -u +%FT%TZ)" "$1" "$2"; }
die() { log error "$1"; exit 1; }

# --- Preflight -------------------------------------------------------------
command -v pg_dump >/dev/null || die "pg_dump missing"
command -v age >/dev/null     || die "age missing"
[ -n "${AGE_RECIPIENT:-}" ]   || die "AGE_RECIPIENT not set"
[ -d "$BACKUP_DIR" ]          || die "BACKUP_DIR $BACKUP_DIR does not exist"
[ -w "$BACKUP_DIR" ]          || die "BACKUP_DIR $BACKUP_DIR not writable"
pg_isready -q || die "database not reachable at $PGHOST:$PGPORT"

# --- Dump + encrypt (streamed; no plaintext dump ever hits disk) -----------
out="$BACKUP_DIR/pulsebase-$(date -u +%F).dump.age"
tmp="$out.tmp"
log info "backup.start file=$(basename "$out") db=$PGDATABASE"
if pg_dump -Fc "$PGDATABASE" | age -r "$AGE_RECIPIENT" -o "$tmp"; then
  mv "$tmp" "$out"
  log info "backup.ok file=$(basename "$out") bytes=$(wc -c < "$out" | tr -d ' ')"
else
  rm -f "$tmp"
  die "pg_dump|age pipeline failed"
fi

# --- Retention -------------------------------------------------------------
removed=$(find "$BACKUP_DIR" -name 'pulsebase-*.dump.age' -mtime +"$BACKUP_RETENTION_DAYS" -print -delete | wc -l | tr -d ' ')
log info "retention.done removed=$removed keep_days=$BACKUP_RETENTION_DAYS"

# --- Optional offsite copy (3-2-1 rule) ------------------------------------
if [ -n "$RCLONE_REMOTE" ]; then
  command -v rclone >/dev/null || die "RCLONE_REMOTE set but rclone missing in image"
  if rclone copy "$BACKUP_DIR" "$RCLONE_REMOTE" --max-age 24h --include 'pulsebase-*.dump.age'; then
    log info "offsite.ok remote=$RCLONE_REMOTE"
  else
    die "rclone copy failed"
  fi
fi

log info "backup.done"
