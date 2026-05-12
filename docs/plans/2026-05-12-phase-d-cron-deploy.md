# Phase Г: Cron + Telegram alerts + backup на app server — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) или superpowers:executing-plans. Шаги используют чекбоксы (`- [ ]`).

**Goal:** на app server `timeweb` (77.233.212.61, root) задеплоить `wb-logistics-toolkit` в `/opt/wb-logistics-toolkit/`, настроить ежедневный cron-сбор тарифов по двум кабинетам (OOO + IP), еженедельный backup SQLite-БД с ротацией 8 копий, daily logrotate, и Telegram-алерт на exit ≠ 0 через `@wookiee_alerts_bot`.

**Architecture:** Wrapper-скрипт `deploy/cron_wrapper.sh` оборачивает любой cron-job: redirect stdout/stderr в `/var/log/wb-toolkit/<task>.log`, ловит exit code, при ≠ 0 шлёт сообщение в Telegram через `TELEGRAM_ALERTS_BOT_TOKEN` + `TELEGRAM_ALERTS_CHAT_ID`. `deploy/backup.sh` — еженедельный `cp` SQLite-файла в `/var/backups/wb_toolkit/` с ротацией старше 56 дней. `deploy/logrotate.conf` — daily/keep 14/compress. `deploy/crontab.md` — документация записей (ставятся через `crontab -e` вручную, не auto-installed).

**Tech Stack:** bash, sqlite3, cron, logrotate, curl (Telegram API). Никаких новых Python-зависимостей.

**Spec:** [docs/specs/2026-05-09-finalize-v1-design.md](../specs/2026-05-09-finalize-v1-design.md) §1.4, §5 Фаза Г.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `deploy/cron_wrapper.sh` | Create | wrapper-скрипт: log + Telegram alert on exit ≠ 0 |
| `deploy/backup.sh` | Create | weekly SQLite backup + ротация 8 недель |
| `deploy/logrotate.conf` | Create | logrotate-конфиг для `/var/log/wb-toolkit/` |
| `deploy/crontab.md` | Create | документация cron-записей (текст для `crontab -e`) |
| `deploy/README.md` | Create | пошаговый bootstrap нового сервера + операции |
| `.env.example` | Modify | добавить `TELEGRAM_ALERTS_BOT_TOKEN`, `TELEGRAM_ALERTS_CHAT_ID` |

**Не трогаем:**
- `audit/etl/tariff_collector.py` — уже принимает `--cabinet`, на этом этапе не модифицируем
- `shared/db.py` — без изменений
- Production-сервер только через SSH `timeweb`; локально только пишем код

---

## Pre-flight (для оператора, не для subagent)

Перед запуском плана у оператора должны быть готовы:

- **Telegram bot token** — `TELEGRAM_ALERTS_BOT_TOKEN` для `@wookiee_alerts_bot` (уже существует в основной Wookiee-инфре)
- **Telegram chat id** — `TELEGRAM_ALERTS_CHAT_ID` куда слать алерты
- **WB tokens** — `WB_TOKEN_OOO` и `WB_TOKEN_IP` (Статистика + Контент + Аналитика + Тарифы)
- SSH-доступ к `timeweb` (`ssh timeweb` → должно работать без пароля; уже настроено)

Если хоть один пункт неясен — STOP и спроси.

---

## Branch Setup

- [ ] **Step 0.1: Создать ветку из main**

```bash
cd ~/Projects/wb-logistics-toolkit
git checkout main
git pull --ff-only
git status                                    # clean
git log --oneline -3                          # ожидаем 1b22fde (Phase В merge)
git checkout -b feat/phase-d-cron-deploy
```

- [ ] **Step 0.2: Baseline pytest**

```bash
.venv/bin/pytest -q
```

Expected: ≥174 passed, 0 failed.

---

## Task 1: `deploy/cron_wrapper.sh` — log + Telegram alert

**Files:**
- Create: `deploy/cron_wrapper.sh`

- [ ] **Step 1.1: Создать `deploy/cron_wrapper.sh`**

```bash
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
```

- [ ] **Step 1.2: chmod +x**

```bash
chmod +x deploy/cron_wrapper.sh
```

- [ ] **Step 1.3: shellcheck**

```bash
shellcheck deploy/cron_wrapper.sh
```

Expected: exit 0, no warnings. Если `shellcheck` не установлен — `brew install shellcheck` локально.

- [ ] **Step 1.4: Local dry-run success path**

Имитируем успешный таск (no Telegram call):

```bash
mkdir -p /tmp/wb-test-deploy/{logs,repo}
cp deploy/cron_wrapper.sh /tmp/wb-test-deploy/repo/cron_wrapper.sh
cd /tmp/wb-test-deploy/repo
sed -i.bak 's|REPO_ROOT="/opt/wb-logistics-toolkit"|REPO_ROOT="/tmp/wb-test-deploy/repo"|' cron_wrapper.sh
sed -i.bak 's|LOG_DIR="/var/log/wb-toolkit"|LOG_DIR="/tmp/wb-test-deploy/logs"|' cron_wrapper.sh
./cron_wrapper.sh smoke-success /usr/bin/true
echo "Exit: $?"
cat /tmp/wb-test-deploy/logs/smoke-success.log
cd ~/Projects/wb-logistics-toolkit
rm -rf /tmp/wb-test-deploy
```

Expected:
- Exit: 0
- Лог содержит `start: smoke-success`, `end: smoke-success exit=0`

- [ ] **Step 1.5: Local dry-run failure path (без реального Telegram-call)**

```bash
mkdir -p /tmp/wb-test-deploy/{logs,repo}
cp deploy/cron_wrapper.sh /tmp/wb-test-deploy/repo/cron_wrapper.sh
cd /tmp/wb-test-deploy/repo
sed -i.bak 's|REPO_ROOT="/opt/wb-logistics-toolkit"|REPO_ROOT="/tmp/wb-test-deploy/repo"|' cron_wrapper.sh
sed -i.bak 's|LOG_DIR="/var/log/wb-toolkit"|LOG_DIR="/tmp/wb-test-deploy/logs"|' cron_wrapper.sh
# .env с заведомо ложными токенами — curl уйдёт но Telegram отбросит 401, не страшно для dry-run
echo 'TELEGRAM_ALERTS_BOT_TOKEN=0000:invalid' > .env
echo 'TELEGRAM_ALERTS_CHAT_ID=0' >> .env
./cron_wrapper.sh smoke-fail /usr/bin/false || echo "Exit: $?"
cat /tmp/wb-test-deploy/logs/smoke-fail.log
cd ~/Projects/wb-logistics-toolkit
rm -rf /tmp/wb-test-deploy
```

Expected:
- Exit: 1
- Лог содержит `exit=1`
- Лог содержит либо HTTP-ответ Telegram (`{"ok":false,...}`), либо `WARN: Telegram alert failed`

- [ ] **Step 1.6: Commit**

```bash
git add deploy/cron_wrapper.sh
git commit -m "feat(deploy): cron wrapper with log + Telegram alert on failure"
```

---

## Task 2: `deploy/backup.sh` — weekly SQLite backup

**Files:**
- Create: `deploy/backup.sh`

- [ ] **Step 2.1: Создать `deploy/backup.sh`**

```bash
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
```

- [ ] **Step 2.2: chmod + shellcheck**

```bash
chmod +x deploy/backup.sh
shellcheck deploy/backup.sh
```

Expected: exit 0, no warnings.

- [ ] **Step 2.3: Local dry-run**

```bash
mkdir -p /tmp/wb-backup-test/{src,dest}
sqlite3 /tmp/wb-backup-test/src/wb_toolkit.db "CREATE TABLE t (id int); INSERT INTO t VALUES (1);"
cp deploy/backup.sh /tmp/wb-backup-test/backup.sh
sed -i.bak 's|SRC="/opt/wb-logistics-toolkit/data/wb_toolkit.db"|SRC="/tmp/wb-backup-test/src/wb_toolkit.db"|' /tmp/wb-backup-test/backup.sh
sed -i.bak 's|DEST_DIR="/var/backups/wb_toolkit"|DEST_DIR="/tmp/wb-backup-test/dest"|' /tmp/wb-backup-test/backup.sh
bash /tmp/wb-backup-test/backup.sh
ls -la /tmp/wb-backup-test/dest/
sqlite3 /tmp/wb-backup-test/dest/wb_toolkit-*.db "SELECT * FROM t;"
rm -rf /tmp/wb-backup-test
```

Expected: файл `wb_toolkit-YYYY-MM-DD.db` существует, `SELECT * FROM t` возвращает `1`.

- [ ] **Step 2.4: Commit**

```bash
git add deploy/backup.sh
git commit -m "feat(deploy): weekly SQLite backup with 8-week rotation"
```

---

## Task 3: `deploy/logrotate.conf`

**Files:**
- Create: `deploy/logrotate.conf`

- [ ] **Step 3.1: Создать `deploy/logrotate.conf`**

```
/var/log/wb-toolkit/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

- [ ] **Step 3.2: Dry-run validation**

```bash
logrotate -d deploy/logrotate.conf 2>&1 | head -30 || echo "logrotate not installed locally — skip; will validate on server"
```

Expected: либо logrotate показывает план без ошибок, либо команда отсутствует локально (нормально для macOS, проверим на сервере).

- [ ] **Step 3.3: Commit**

```bash
git add deploy/logrotate.conf
git commit -m "feat(deploy): logrotate config (daily, keep 14, compress)"
```

---

## Task 4: `deploy/crontab.md` — документация cron-записей

**Files:**
- Create: `deploy/crontab.md`

- [ ] **Step 4.1: Создать `deploy/crontab.md`**

````markdown
# wb-logistics-toolkit — cron entries (app server)

Установить через `crontab -e` от root на `timeweb`. Эти записи **НЕ устанавливаются автоматически** — каждый раз руками после `git pull`, если расписание поменялось.

```cron
# Daily tariff snapshot — OOO (06:00 UTC = 09:00 MSK)
0 6 * * * /opt/wb-logistics-toolkit/deploy/cron_wrapper.sh tariff-ooo /opt/wb-logistics-toolkit/.venv/bin/python /opt/wb-logistics-toolkit/audit/etl/tariff_collector.py --cabinet ooo

# Daily tariff snapshot — IP (06:05 UTC)
5 6 * * * /opt/wb-logistics-toolkit/deploy/cron_wrapper.sh tariff-ip /opt/wb-logistics-toolkit/.venv/bin/python /opt/wb-logistics-toolkit/audit/etl/tariff_collector.py --cabinet ip

# Weekly SQLite backup (Sunday 02:00 UTC)
0 2 * * 0 /opt/wb-logistics-toolkit/deploy/cron_wrapper.sh backup /opt/wb-logistics-toolkit/deploy/backup.sh

# Daily logrotate (03:00 UTC)
0 3 * * * /usr/sbin/logrotate -s /var/lib/logrotate/wb-toolkit.state /opt/wb-logistics-toolkit/deploy/logrotate.conf
```

## Проверка

```bash
crontab -l                         # должны быть 4 строки выше
tail -f /var/log/wb-toolkit/*.log  # смотрим, что cron реально пишет
```

## Forced run (без ожидания cron)

```bash
/opt/wb-logistics-toolkit/deploy/cron_wrapper.sh tariff-ooo \
  /opt/wb-logistics-toolkit/.venv/bin/python \
  /opt/wb-logistics-toolkit/audit/etl/tariff_collector.py --cabinet ooo
```

Expected exit 0. В случае exit ≠ 0 → Telegram-алерт в `@wookiee_alerts_bot`.
````

- [ ] **Step 4.2: Commit**

```bash
git add deploy/crontab.md
git commit -m "docs(deploy): document cron entries and ops procedures"
```

---

## Task 5: `.env.example` — добавить Telegram-переменные

**Files:**
- Modify: `.env.example`

- [ ] **Step 5.1: Добавить две строки в `.env.example`**

OLD:
```
# Local SQLite for tariff history
WB_TOOLKIT_DB_PATH=data/wb_toolkit.db
```

NEW (добавить блок в конец файла):
```
# Local SQLite for tariff history
WB_TOOLKIT_DB_PATH=data/wb_toolkit.db

# Telegram alerts (cron wrapper sends on exit != 0)
TELEGRAM_ALERTS_BOT_TOKEN=
TELEGRAM_ALERTS_CHAT_ID=
```

- [ ] **Step 5.2: Sanity**

```bash
grep -E "TELEGRAM_ALERTS_" .env.example
```

Expected: видим обе строки.

- [ ] **Step 5.3: Commit**

```bash
git add .env.example
git commit -m "feat(deploy): add TELEGRAM_ALERTS_* env vars to .env.example"
```

---

## Task 6: `deploy/README.md` — пошаговый bootstrap нового сервера

**Files:**
- Create: `deploy/README.md`

- [ ] **Step 6.1: Создать `deploy/README.md`**

````markdown
# Server bootstrap — wb-logistics-toolkit

Запуск с нуля на новом сервере (root or sudo).

## 1. Clone + venv

```bash
mkdir -p /opt
cd /opt
git clone https://github.com/danila-matveev/wb-logistics-toolkit.git
cd wb-logistics-toolkit
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 2. `.env`

```bash
cp .env.example .env
chmod 600 .env
nano .env   # заполнить WB_TOKEN_OOO, WB_TOKEN_IP, TELEGRAM_ALERTS_BOT_TOKEN, TELEGRAM_ALERTS_CHAT_ID
```

## 3. SQLite — bootstrap данных тарифов

**Вариант A** (предпочтительный, если есть локальный `data/wb_toolkit.db` с историей):

```bash
# На локальной машине:
scp ~/Projects/wb-logistics-toolkit/data/wb_toolkit.db timeweb:/opt/wb-logistics-toolkit/data/wb_toolkit.db
```

**Вариант B** (с нуля, только today):

```bash
.venv/bin/python audit/etl/tariff_collector.py --cabinet ooo
.venv/bin/python audit/etl/tariff_collector.py --cabinet ip
```

Проверить:

```bash
sqlite3 data/wb_toolkit.db 'SELECT count(*) FROM wb_tariffs;'
sqlite3 data/wb_toolkit.db 'PRAGMA journal_mode;'   # ожидаем wal
```

## 4. check_setup

```bash
.venv/bin/python check_setup.py
```

Expected: 7/7 ✅.

## 5. Каталоги для логов и бэкапов

```bash
mkdir -p /var/log/wb-toolkit /var/backups/wb_toolkit
```

## 6. Cron

См. `deploy/crontab.md`. Записи копируются в `crontab -e` руками.

## 7. Smoke: forced wrapper run

**Success path** (Telegram молчит):

```bash
/opt/wb-logistics-toolkit/deploy/cron_wrapper.sh tariff-ooo \
  /opt/wb-logistics-toolkit/.venv/bin/python \
  /opt/wb-logistics-toolkit/audit/etl/tariff_collector.py --cabinet ooo
echo "Exit: $?"
tail -5 /var/log/wb-toolkit/tariff-ooo.log
```

Expected: Exit: 0, лог показывает `end: tariff-ooo exit=0`, в Telegram **никаких** сообщений.

**Failure path** (Telegram должен ответить):

```bash
WB_TOKEN_OOO=invalid \
/opt/wb-logistics-toolkit/deploy/cron_wrapper.sh tariff-ooo \
  /opt/wb-logistics-toolkit/.venv/bin/python \
  /opt/wb-logistics-toolkit/audit/etl/tariff_collector.py --cabinet ooo
echo "Exit: $?"
tail -10 /var/log/wb-toolkit/tariff-ooo.log
```

Expected: Exit ≠ 0, лог содержит `exit=1` и Telegram-ответ `{"ok":true,"result":{...}}`, в `@wookiee_alerts_bot` пришло сообщение со стеком ошибки.

## 8. Backup smoke

```bash
/opt/wb-logistics-toolkit/deploy/backup.sh
ls -la /var/backups/wb_toolkit/
```

Expected: один `wb_toolkit-YYYY-MM-DD.db` файл с тем же размером, что и `data/wb_toolkit.db`.

## 9. Logrotate dry-run

```bash
logrotate -d /opt/wb-logistics-toolkit/deploy/logrotate.conf
```

Expected: план ротации без ошибок, состояние `/var/lib/logrotate/wb-toolkit.state` создаётся при реальном запуске.
````

- [ ] **Step 6.2: Commit**

```bash
git add deploy/README.md
git commit -m "docs(deploy): server bootstrap guide"
```

---

## Task 7: SSH bootstrap на app server (ops, без code-commit'а)

**Цель:** выполнить шаги из `deploy/README.md` на `timeweb` для текущей ветки, проверить smoke-paths.

> **Важно:** этот таск не производит code-commit'ов. Subagent выполняет команды по SSH, фиксирует output в виде структурированного отчёта в финальном message. Если что-то идёт не так — BLOCKED, escalate с tail логов и шагом, где упало.

- [ ] **Step 7.1: Pre-flight**

```bash
ssh timeweb 'hostname && uname -a && python3.11 --version 2>&1 || python3 --version 2>&1; which logrotate sqlite3 curl; ls /opt 2>&1'
```

Expected:
- hostname отображается (77.233.212.61 или его alias)
- python3.11 (или python3 версии ≥3.11) есть
- `logrotate`, `sqlite3`, `curl` — все установлены (стандарт для timeweb)
- `/opt` существует, без `wb-logistics-toolkit/` внутри (свежий деплой). Если каталог уже есть — STOP, эскалировать оператору.

- [ ] **Step 7.2: Clone + venv (под root на timeweb)**

```bash
ssh timeweb 'cd /opt && git clone --branch feat/phase-d-cron-deploy https://github.com/danila-matveev/wb-logistics-toolkit.git'
ssh timeweb 'cd /opt/wb-logistics-toolkit && python3.11 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r requirements.txt'
```

Expected: оба exit 0, `.venv/bin/python` существует.

- [ ] **Step 7.3: `.env` через scp (секреты не идут через промт)**

Pre-check: оператор перед запуском плана должен убедиться, что в локальном `~/Projects/wb-logistics-toolkit/.env` присутствуют 4 переменных:
- `WB_TOKEN_OOO=eyJ...`
- `WB_TOKEN_IP=eyJ...`
- `TELEGRAM_ALERTS_BOT_TOKEN=...`
- `TELEGRAM_ALERTS_CHAT_ID=...`

Subagent проверяет наличие:

```bash
grep -cE "^(WB_TOKEN_OOO|WB_TOKEN_IP|TELEGRAM_ALERTS_BOT_TOKEN|TELEGRAM_ALERTS_CHAT_ID)=" ~/Projects/wb-logistics-toolkit/.env
```

Expected: `4`. Если меньше — STOP, эскалировать (`NEEDS_CONTEXT: оператор не заполнил .env`).

Если 4 — копируем:

```bash
scp ~/Projects/wb-logistics-toolkit/.env timeweb:/opt/wb-logistics-toolkit/.env
ssh timeweb 'chmod 600 /opt/wb-logistics-toolkit/.env && head -1 /opt/wb-logistics-toolkit/.env'
```

Expected: `head -1` показывает первую строку (любая, для подтверждения, что файл существует и читается).

- [ ] **Step 7.4: SQLite — scp с локалки**

С локальной машины (НЕ через ssh):

```bash
scp ~/Projects/wb-logistics-toolkit/data/wb_toolkit.db timeweb:/opt/wb-logistics-toolkit/data/wb_toolkit.db
```

Проверка на сервере:

```bash
ssh timeweb 'cd /opt/wb-logistics-toolkit && sqlite3 data/wb_toolkit.db "SELECT count(*) FROM wb_tariffs;" && sqlite3 data/wb_toolkit.db "PRAGMA journal_mode;"'
```

Expected: count(*) ≥ 38000 (~38561 после Phase А миграции); journal_mode → `wal`.

- [ ] **Step 7.5: check_setup**

```bash
ssh timeweb 'cd /opt/wb-logistics-toolkit && .venv/bin/python check_setup.py'
```

Expected: 7/7 ✅. Если ❌ на любом из 7 — STOP и эскалировать (root cause).

- [ ] **Step 7.6: Каталоги для логов и бэкапов**

```bash
ssh timeweb 'mkdir -p /var/log/wb-toolkit /var/backups/wb_toolkit'
```

- [ ] **Step 7.7: Smoke success**

```bash
ssh timeweb '/opt/wb-logistics-toolkit/deploy/cron_wrapper.sh tariff-ooo /opt/wb-logistics-toolkit/.venv/bin/python /opt/wb-logistics-toolkit/audit/etl/tariff_collector.py --cabinet ooo; echo "Exit: $?"'
ssh timeweb 'tail -10 /var/log/wb-toolkit/tariff-ooo.log'
```

Expected:
- Exit: 0
- Лог показывает `start`, тарифы успешно записаны (новая строка или upsert на сегодняшнюю дату), `exit=0`
- В `@wookiee_alerts_bot` НИЧЕГО не пришло (оператор проверяет на телефоне)

- [ ] **Step 7.8: Smoke failure (через несуществующий кабинет — wrapper'ный `source .env` не перезатрёт триггер)**

```bash
ssh timeweb '/opt/wb-logistics-toolkit/deploy/cron_wrapper.sh tariff-fail-test /opt/wb-logistics-toolkit/.venv/bin/python /opt/wb-logistics-toolkit/audit/etl/tariff_collector.py --cabinet nonexistent_cabinet_xyz; echo "Exit: $?"'
ssh timeweb 'tail -20 /var/log/wb-toolkit/tariff-fail-test.log'
```

`get_cabinet("nonexistent_cabinet_xyz")` поднимет `KeyError` → exit 1 → wrapper увидит ненулевой exit → отправит Telegram-алерт.

Expected:
- Exit: 1
- Лог содержит `exit=1` и Telegram response `{"ok":true,...}` (или WARN если что-то не так с переменными)
- В `@wookiee_alerts_bot` пришло сообщение с заголовком `wb-logistics-toolkit / tariff-fail-test / exit:1 / ...`

Оператор подтверждает приход сообщения в Telegram перед переходом к Step 7.9.

Cleanup test log:

```bash
ssh timeweb 'rm /var/log/wb-toolkit/tariff-fail-test.log'
```

- [ ] **Step 7.9: Backup smoke**

```bash
ssh timeweb '/opt/wb-logistics-toolkit/deploy/backup.sh'
ssh timeweb 'ls -la /var/backups/wb_toolkit/'
```

Expected: один файл `wb_toolkit-YYYY-MM-DD.db`, размер ≈ исходному.

- [ ] **Step 7.10: Logrotate dry-run**

```bash
ssh timeweb 'logrotate -d /opt/wb-logistics-toolkit/deploy/logrotate.conf 2>&1 | head -30'
```

Expected: план без ошибок.

- [ ] **Step 7.11: Install crontab**

```bash
ssh timeweb 'crontab -l 2>/dev/null > /tmp/cron-current.txt; cat /opt/wb-logistics-toolkit/deploy/crontab.md | grep -E "^[0-9*]" >> /tmp/cron-current.txt; crontab /tmp/cron-current.txt; crontab -l'
```

Expected: `crontab -l` показывает 4 новые строки (tariff-ooo, tariff-ip, backup, logrotate). Если уже были другие записи — сохраняются.

> **Внимание:** если на сервере есть autopull-cron Wookiee (memory упоминает `cron */5 под deploy`) — он, скорее всего, в crontab другого пользователя (`deploy`), не root. Проверить через `sudo crontab -u deploy -l` (или просто `crontab -u deploy -l` под root). Не трогать чужие записи.

- [ ] **Step 7.12: Финальная сводка subagent**

Subagent выдаёт структурированный отчёт:

```
SERVER BOOTSTRAP REPORT
=======================
Host: <hostname>
Repo path: /opt/wb-logistics-toolkit
Branch: feat/phase-d-cron-deploy
Commit: <hash>
SQLite rows: <count>
check_setup: <X>/7
Smoke success: exit=<0>
Smoke failure: exit=<1>, Telegram alert: <received: yes/no>
Backup: <filename, bytes>
Logrotate dry-run: <ok/issue>
Crontab installed: <yes/no>, lines: <N>
```

Если хоть один пункт не зелёный — BLOCKED.

---

## Task 8: Push + PR

- [ ] **Step 8.1: Финальный pytest (на локалке, чтобы убедиться, что код в ветке не сломался)**

```bash
cd ~/Projects/wb-logistics-toolkit
git status   # only deploy/* и .env.example в коммитах
.venv/bin/pytest -q
```

Expected: ≥174 passed, 0 failed.

- [ ] **Step 8.2: Push + PR**

```bash
git push -u origin feat/phase-d-cron-deploy
gh pr create --title "Phase Г: cron + Telegram alerts + backup on app server" --body "$(cat <<'EOF'
## Summary
- `deploy/cron_wrapper.sh` — bash wrapper для cron-job'ов: redirect в `/var/log/wb-toolkit/<task>.log`, Telegram-алерт через `@wookiee_alerts_bot` на exit != 0.
- `deploy/backup.sh` — weekly SQLite backup через `sqlite3 .backup` (safe для WAL) с ротацией 8 недель.
- `deploy/logrotate.conf` — daily / keep 14 / compress.
- `deploy/crontab.md` — документация 4 cron-записей (tariff-ooo, tariff-ip, backup, logrotate).
- `deploy/README.md` — пошаговый bootstrap нового сервера + smoke procedures.
- `.env.example` — добавлены `TELEGRAM_ALERTS_BOT_TOKEN` и `TELEGRAM_ALERTS_CHAT_ID`.

## Bootstrap результаты
- Сервер: `timeweb` (77.233.212.61), путь `/opt/wb-logistics-toolkit/`
- check_setup: 7/7 ✅
- SQLite migrated: ~38561 строк, journal_mode=wal
- Smoke success: exit 0, Telegram молчит
- Smoke failure: exit 1, Telegram-алерт пришёл в `@wookiee_alerts_bot`
- Backup smoke: `/var/backups/wb_toolkit/wb_toolkit-YYYY-MM-DD.db` создан
- Crontab: 4 строки установлены, `crontab -l` подтверждает

## Plan / Spec
- Spec: `docs/specs/2026-05-09-finalize-v1-design.md` §1.4, §5 Фаза Г
- Plan: `docs/plans/2026-05-12-phase-d-cron-deploy.md`

## Acceptance
- [x] pytest ≥174 passed, 0 failed
- [x] `deploy/cron_wrapper.sh`, `deploy/backup.sh`, `deploy/logrotate.conf`, `deploy/crontab.md`, `deploy/README.md` существуют
- [x] `.env.example` содержит `TELEGRAM_ALERTS_*`
- [x] Server: check_setup 7/7, cron установлен, smoke success+failure прошли

## Test plan
- [ ] Reviewer: `shellcheck deploy/*.sh` — expect 0 warnings
- [ ] Reviewer: `pytest -q` — expect ≥174 passed
- [ ] Phase Д запустит full smoke на кабинете IP (audit + Phase 1/2/3 localization)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 8.3: После мерджа PR (пользователь команду даёт) — pull на сервере**

```bash
ssh timeweb 'cd /opt/wb-logistics-toolkit && git checkout main && git pull --ff-only && git log --oneline -3'
```

Expected: ветка `main`, новый squash-коммит Phase Г на вершине.

---

## Acceptance criteria этого плана

- [ ] `pytest -q` → ≥174 passed, 0 failed
- [ ] 5 файлов в `deploy/` существуют и проходят `shellcheck`
- [ ] `.env.example` содержит `TELEGRAM_ALERTS_BOT_TOKEN` + `TELEGRAM_ALERTS_CHAT_ID`
- [ ] Сервер: `/opt/wb-logistics-toolkit/` существует, venv установлен, `check_setup.py` → 7/7
- [ ] Сервер: `data/wb_toolkit.db` мигрирован, `PRAGMA journal_mode` → `wal`, count(*) ≥ 38000
- [ ] Сервер: `crontab -l` (root) показывает 4 записи (tariff-ooo, tariff-ip, backup, logrotate)
- [ ] Сервер: smoke success — Telegram молчит; smoke failure — Telegram-алерт пришёл
- [ ] Сервер: `/var/backups/wb_toolkit/` содержит хотя бы один файл после `backup.sh`
- [ ] Сервер: `logrotate -d` показывает план без ошибок
- [ ] PR `feat/phase-d-cron-deploy` merged в main

После мерджа этого плана — следующий: **Фаза Д — Smoke на кабинете ИП** (прогон всех 4 артефактов: audit + Phase 1/2/3 localization для IP).
