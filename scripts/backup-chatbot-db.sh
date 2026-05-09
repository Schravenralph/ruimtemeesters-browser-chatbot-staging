#!/usr/bin/env bash
# Daily backup of chatbot-db (rmchatbot + litellm databases) to /mnt/storagebox.
#
# Wired to cron via /etc/cron.d/rm-chatbot-db-backup at 3:30am daily — runs
# after the existing storagebox-backup at 3:00 so the two don't fight over
# postgres CPU.
#
# Existence prevents future repeats of the 2026-05-09 incident where the
# chatbot DB had no recoverable backup. The host-level pg_dumpall pipeline
# (/usr/local/bin/backup-to-storagebox.sh) only reaches the Databank's
# postgres container, so the dockerized chatbot-db needed its own.
#
# Restore: pick the latest dump and replay against an empty database, e.g.:
#   docker exec -i rm-chatbot-db psql -U rmchatbot -d <db> < <(zcat <file>)
#
set -euo pipefail

CONTAINER="${CHATBOT_DB_CONTAINER:-rm-chatbot-db}"
DEST="${BACKUP_DIR:-/mnt/storagebox/vps-data/backups/postgres/rm-chatbot}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DB_USER="${POSTGRES_USER:-rmchatbot}"
DBS=("rmchatbot" "litellm")
DATE=$(date +%Y-%m-%d)
LOG="${LOG_FILE:-${HOME}/.local/state/rm-chatbot-db-backup.log}"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG" >&2; }

# Pre-flight
mountpoint -q /mnt/storagebox || {
  log "ERROR: storage box not mounted; aborting"
  exit 1
}

# `docker inspect` succeeds for any state (running, exited, paused) — only
# .State.Running tells us we can actually exec against it. Without this
# stricter check, a stopped container would let the loop "skip" every DB
# (because exec fails silently into the EXISTS=`` branch) and the script
# would exit 0 with zero backups produced — silent data-loss risk.
RUNNING=$(docker inspect --format '{{.State.Running}}' "$CONTAINER" 2>/dev/null || echo "false")
if [[ "$RUNNING" != "true" ]]; then
  log "ERROR: container $CONTAINER not running (state='$RUNNING'); aborting"
  exit 2
fi

mkdir -p "$DEST"

# Dump each known database — skip silently if it does not yet exist (e.g. a
# fresh install before LiteLLM has been provisioned for the first time).
for DB in "${DBS[@]}"; do
  EXISTS=$(
    docker exec "$CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
      "SELECT 1 FROM pg_database WHERE datname='${DB}'" 2>/dev/null \
      | tr -d '[:space:]' || echo ""
  )
  if [[ "$EXISTS" != "1" ]]; then
    log "skip: database '${DB}' does not exist"
    continue
  fi

  OUT="${DEST}/${CONTAINER}_${DB}_${DATE}.sql.gz"
  if docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB" \
       --clean --if-exists --no-owner --no-privileges \
       2>>"$LOG" \
       | gzip > "$OUT"; then
    SIZE=$(du -h "$OUT" | cut -f1)
    log "ok: ${DB} → ${OUT} (${SIZE})"
  else
    log "ERROR: pg_dump failed for '${DB}'"
    rm -f "$OUT"
  fi
done

# Prune dumps older than RETENTION_DAYS days. Wrap the whole pipeline in
# `|| log "WARN..."` so a transient prune failure (network-mount glitch on
# the storagebox, stale handle, etc.) does NOT mask the success of the
# backups above. Cron should report failure only when the actual dumps
# fail, not when housekeeping does.
{
  find "$DEST" -name "${CONTAINER}_*.sql.gz" -type f -mtime "+${RETENTION_DAYS}" \
    -print -delete 2>>"$LOG" \
    | while read -r f; do log "pruned: $f"; done
} || log "WARN: prune step failed (non-fatal; backups above succeeded)"

log "complete"
