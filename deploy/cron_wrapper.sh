#!/usr/bin/env bash
# Wrapper for cron jobs in wb-logistics-toolkit.
# Logs stdout/stderr to /var/log/wb-toolkit/<task>.log. On exit != 0 sends a
# Telegram alert via TELEGRAM_ALERTS_BOT_TOKEN/CHAT_ID from .env.
#
# Usage:
#   /opt/wb-logistics-toolkit/deploy/cron_wrapper.sh <task-name> <command...>
#
# Example:
#   /opt/wb-logistics-toolkit/deploy/cron_wrapper.sh tariff-ooo \
#     .venv/bin/python audit/etl/tariff_collector.py --cabinet ooo
set -euo pipefail

TASK_NAME="${1:?usage: cron_wrapper.sh <task-name> <command...>}"
shift

REPO_ROOT="/opt/wb-logistics-toolkit"
LOG_DIR="/var/log/wb-toolkit"
LOG_FILE="${LOG_DIR}/${TASK_NAME}.log"

mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

# Load .env (file must have perms 600, owned by cron user)
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

TS_START="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo "===== ${TS_START} start: ${TASK_NAME} =====" >> "$LOG_FILE"

set +e
"$@" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
set -e

TS_END="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo "===== ${TS_END} end: ${TASK_NAME} exit=${EXIT_CODE} =====" >> "$LOG_FILE"

if [[ $EXIT_CODE -ne 0 ]]; then
    if [[ -n "${TELEGRAM_ALERTS_BOT_TOKEN:-}" && -n "${TELEGRAM_ALERTS_CHAT_ID:-}" ]]; then
        MSG=$(printf 'wb-logistics-toolkit\nhost: %s\ntask: %s\nexit: %d\nts: %s\nlog: %s\nlast lines:\n%s' \
            "$(hostname)" "$TASK_NAME" "$EXIT_CODE" "$TS_END" "$LOG_FILE" \
            "$(tail -n 20 "$LOG_FILE" | sed 's/[`*_]/\\&/g')")
        curl -fsS -X POST \
            "https://api.telegram.org/bot${TELEGRAM_ALERTS_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_ALERTS_CHAT_ID}" \
            --data-urlencode "text=${MSG}" \
            >> "$LOG_FILE" 2>&1 \
            || echo "WARN: Telegram alert failed (curl exit $?)" >> "$LOG_FILE"
    else
        echo "WARN: TELEGRAM_ALERTS_BOT_TOKEN/CHAT_ID not set, no alert sent" >> "$LOG_FILE"
    fi
fi

exit $EXIT_CODE
