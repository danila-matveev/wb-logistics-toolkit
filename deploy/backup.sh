#!/usr/bin/env bash
# Weekly SQLite backup with 8-week rotation.
# Uses `sqlite3 .backup` (safe under concurrent writes in WAL mode) instead of cp.
set -euo pipefail

SRC="/opt/wb-logistics-toolkit/data/wb_toolkit.db"
DEST_DIR="/var/backups/wb_toolkit"
RETAIN_DAYS=56

mkdir -p "$DEST_DIR"

if [[ ! -f "$SRC" ]]; then
    echo "ERROR: source DB not found: $SRC" >&2
    exit 1
fi

DEST="${DEST_DIR}/wb_toolkit-$(date +%F).db"
sqlite3 "$SRC" ".backup '${DEST}'"
echo "Backup written: ${DEST} ($(stat -c%s "$DEST" 2>/dev/null || stat -f%z "$DEST") bytes)"

find "$DEST_DIR" -name 'wb_toolkit-*.db' -type f -mtime "+${RETAIN_DAYS}" -delete
echo "Rotation done (kept ≤${RETAIN_DAYS}d)"
