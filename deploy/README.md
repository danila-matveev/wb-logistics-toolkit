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
