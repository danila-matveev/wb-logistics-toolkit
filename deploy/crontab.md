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
