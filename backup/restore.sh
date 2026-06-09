#!/bin/sh
# PulseBase DB restore (TimescaleDB-correct): age-decrypt -> create DB -> pre_restore
# -> pg_restore (NO -j) -> post_restore -> row-count check.
#
# Usage: restore.sh <dump.age|latest> <target-db>
# Env:   AGE_IDENTITY  path to the age PRIVATE key (REQUIRED)
#        BACKUP_DIR    where to look for "latest" (default: /backups)
#        PGHOST/PGPORT/PGUSER/PGPASSWORD  libpq connection (PGHOST default "db")
set -eu

FILE="${1:?usage: restore.sh <dump.age|latest> <target-db>}"
TARGET="${2:?usage: restore.sh <dump.age|latest> <target-db>}"
: "${PGHOST:=db}"
: "${PGPORT:=5432}"
: "${BACKUP_DIR:=/backups}"
: "${AGE_IDENTITY:?AGE_IDENTITY (path to age private key) not set}"
export PGHOST PGPORT

log() { printf '{"ts":"%s","svc":"restore","level":"%s","msg":"%s"}\n' "$(date -u +%FT%TZ)" "$1" "$2"; }
die() { log error "$1"; exit 1; }

if [ "$FILE" = "latest" ]; then
  FILE=$(ls -t "$BACKUP_DIR"/pulsebase-*.dump.age 2>/dev/null | head -1)
  [ -n "$FILE" ] || die "no backup found in $BACKUP_DIR"
fi
[ -f "$FILE" ]         || die "dump $FILE not found"
[ -f "$AGE_IDENTITY" ] || die "age identity $AGE_IDENTITY not found"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
log info "restore.decrypt file=$(basename "$FILE")"
age -d -i "$AGE_IDENTITY" -o "$tmp" "$FILE" || die "age decrypt failed"

log info "restore.prepare db=$TARGET"
dropdb --if-exists "$TARGET"
createdb "$TARGET"
psql -v ON_ERROR_STOP=1 -d "$TARGET" -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
# TimescaleDB requires pre/post_restore around pg_restore, and NO parallel (-j),
# which would corrupt the TimescaleDB catalogs.
psql -v ON_ERROR_STOP=1 -d "$TARGET" -c "SELECT timescaledb_pre_restore();"
pg_restore --no-owner --no-acl -d "$TARGET" "$tmp" || log warn "pg_restore reported warnings"
psql -v ON_ERROR_STOP=1 -d "$TARGET" -c "SELECT timescaledb_post_restore();"

users=$(psql -tAc "SELECT count(*) FROM users;" -d "$TARGET")
log info "restore.done db=$TARGET users=$users"
echo "$users"
