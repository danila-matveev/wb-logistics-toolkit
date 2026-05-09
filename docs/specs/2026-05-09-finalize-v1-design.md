# Finalize v1 — Design

**Status:** approved (pending user re-review of this document)
**Date:** 2026-05-09
**Owner:** CTO/DevOps (Claude)
**Goal:** довести `wb-logistics-toolkit` до состояния «по любому WB-кабинету получить все 4 артефакта (Excel-аудит переплат + 3 фазы локализации) автономно, без внешних SaaS, c регулярным сбором тарифов на сервере»

---

## 0. Контекст

### Что есть на момент старта

- Standalone Python-репо `~/Projects/wb-logistics-toolkit/`, отделено от Wookiee.
- 4 плана реализации завершены, написана документация.
- В этой сессии починили: env autoload, sys.path для audit, WB API host для tariffs (`supplies-api` → `common-api`), async `warehouse_remains`, формат `cards/list` (был баг с `cursor.nmIDs` → пустой `card_dims` → волюм=0).
- Аудит OOO работает E2E: 12 листов Excel, корректная цифра переплаты 4.8 % / 293 836 ₽ на периоде 2026-03-07…2026-05-05.
- Pytest 145/145.
- Локализация Phase 1 (`run_analysis.py`) проверена на OOO.
- Phase 2 (`run_roadmap.py`) и Phase 3 (`run_permutations.py`) — код готов, **не верифицирован end-to-end**.
- `wb_coeff_table` живёт в Supabase (20 строк KTR/KRP).
- `wb_tariffs` живёт в Supabase (61 склад × 60 дней).

### Что мешает считать сервис «готовым»

1. Внешняя зависимость от `supabase.com` для standalone-утилиты — плохой матч.
2. Phase 2/3 локализации не прогнаны на живом API — могут оказаться баги типа того, что был с `warehouse_remains`.
3. Sheets-конфиг рассинхронизирован: код локализации читает `GOOGLE_CREDENTIALS_JSON`, `.env.example` объявляет `GOOGLE_CREDENTIALS_PATH`.
4. `cabinets.yaml::sheet_id` обязательное поле — даже если оператор хочет только Excel, он вынужден возиться с Google API.
5. Нет автоматизации сбора `wb_tariffs` — WB не отдаёт исторические тарифы, без ежедневного snapshot'а аудит за прошлый период деградирует.
6. Документация местами отстаёт от кода (например, scope WB-токена в `docs/setup.md`).

---

## 1. Архитектурные решения

### 1.1. Хранилище

**Решение:** гибрид «KTR/KRP — в коде, `wb_tariffs` — в SQLite-файле».

| Объект | Тип данных | Где живёт |
|---|---|---|
| `COEFF_TABLE` (KTR/KRP по уровням локализации) | статичный справочник, 20 строк, обновляется ~раз в год | Python-литерал в `shared/coeff_table.py`. Изменения через PR + `git diff`. |
| `wb_tariffs` (snapshot тарифов складов) | динамические данные, ~36k строк/год, ~5 МБ | SQLite-файл `data/wb_toolkit.db`. Один писатель (cron), N читателей. |

**Почему не Supabase**: внешний SaaS для standalone-утилиты — ненужная зависимость, мешает packaging для других кабинетов.

**Почему не Postgres на app server**: лишняя инфра (установка, бэкапы, порт, мониторинг) для 5 МБ данных. Когда понадобится full-stack-интерфейс — мигрируем (`INSERT ... SELECT` через Python, ~час работы).

**Почему не CSV/JSON**: запросы по `(warehouse_name, date)` с fill-forward выгоднее в SQL, чем линейный поиск по файлу.

### 1.2. Sheets vs Excel

**Решение:** Excel-fallback по умолчанию, Sheets — опциональная фича для совместной работы.

Логика выбора писателя в `run_*.py`:

```
sheet_id указан в cabinets.yaml (не пустой)?
  ↓ да                               ↓ нет
credentials.json есть и валиден?     ExcelWriter
  ↓ да              ↓ нет
SheetsWriter        ExcelWriter
```

Дополнительно — флаг `--no-sheets` форсирует Excel.

### 1.3. Запуск

**Аудит** (10 минут на download отчёта) — на app server через SSH:

```
ssh timeweb
cd /opt/wb-logistics-toolkit && source .venv/bin/activate
python audit/run_audit.py <cabinet> <from> <to>
# результат в /opt/wb-logistics-toolkit/output/
scp timeweb:/opt/wb-logistics-toolkit/output/*.xlsx ~/Desktop/
```

Причина: `data/wb_toolkit.db` живёт на сервере, постоянно обновляется cron'ом — локально нужны были бы `scp` БД перед каждым запуском.

**Локализация Phase 1** — там же, потому что использует те же тарифы и тот же Python-стек.

### 1.4. Cron на app server

| Задача | Расписание | Команда (через wrapper) |
|---|---|---|
| Snapshot тарифов OOO | ежедневно 06:00 UTC | `python audit/etl/tariff_collector.py --cabinet ooo` |
| Snapshot тарифов ИП | ежедневно 06:05 UTC | `python audit/etl/tariff_collector.py --cabinet ip` |
| Backup БД | еженедельно (вс 02:00 UTC) | `deploy/backup.sh` (cp + ротация 8 недель) |

Wrapper-скрипт `deploy/cron_wrapper.sh`:
- redirect stdout/stderr в `/var/log/wb-toolkit/<task>.log`
- при exit ≠ 0 — алерт через Telegram-бот `@wookiee_alerts_bot` (токен `TELEGRAM_ALERTS_BOT_TOKEN`)
- никакого retry — пользователь сам перезапускает после фикса

### 1.5. Изменение зависимостей

Уходит из `requirements.txt`:
- `supabase>=2.4.0`

Остаётся:
- `httpx`, `pandas`, `openpyxl` — расчёты + Excel
- `google-auth`, `gspread` — Sheets (опционально, не deinstall'ятся, но нужны только при включённом Sheets-флоу)
- `python-dotenv`, `PyYAML` — конфиг
- `pytest`, `pytest-mock` — тесты

`sqlite3` — встроен в Python, дополнительная зависимость не нужна.

### 1.6. Что **не** делаем в v1

Сознательно отложено в backlog v2:

- кэш raw `reportDetailByPeriod` (10 минут на download остаются)
- web-интерфейс / API-обёртка
- автоматизация перестановок (Phase 3) через регулярный cron — пока запуск ручной по кнопке
- Postgres-миграция

---

## 2. Структура репозитория после доработки

```
wb-logistics-toolkit/
├── shared/
│   ├── __init__.py            (autoload .env)
│   ├── coeff_table.py         ← KTR/KRP справочник встроен константой
│   ├── db.py                  ← новый, sqlite3-обёртка (заменяет supabase.py)
│   ├── config.py              ← cabinets.yaml + .env, без изменений
│   └── wb_api/                ← все WB endpoints, без изменений в формате
├── audit/
│   ├── run_audit.py
│   ├── calculators/
│   ├── output/                ← 12 листов Excel
│   └── etl/
│       └── tariff_collector.py    ← пишет в SQLite
├── localization/
│   ├── run_analysis.py        ← Phase 1
│   ├── run_roadmap.py         ← Phase 2
│   ├── run_permutations.py    ← Phase 3
│   ├── calculators/
│   ├── output/                ← новый каталог
│   │   ├── writer.py          ← Protocol + SheetsWriter + ExcelWriter
│   │   ├── analysis_writer.py     (рефакторенный)
│   │   ├── roadmap_writer.py      (рефакторенный)
│   │   └── permutations_writer.py (рефакторенный)
│   └── data/
│       ├── cache/             ← Phase 1 JSON-кэш
│       └── output/            ← Excel-fallback файлы
├── data/
│   └── wb_toolkit.db          ← SQLite, gitignored
├── tests/
│   ├── audit/                 ← существующие
│   ├── localization/          ← + 2 новых (test_run_roadmap, test_run_permutations)
│   └── shared/                ← существующие + db.py тесты
├── scripts/
│   └── migrate_supabase_to_sqlite.py    ← одноразовый, удаляется после прогона
├── deploy/
│   ├── crontab                ← документация cron-записей
│   ├── cron_wrapper.sh        ← обёртка с логом и алертом
│   ├── backup.sh              ← weekly backup БД с ротацией 8 недель
│   └── logrotate.conf         ← конфиг для /etc/logrotate.d/wb-toolkit
├── docs/
│   ├── index.md               ← навигация (создаётся)
│   ├── setup.md               ← переписан без Supabase
│   ├── onboarding-cabinet.md  ← новый, 4-шаговая инструкция
│   ├── deploy.md              ← новый, переустановка с нуля
│   ├── tariffs-storage.md     ← переименован из tariffs-db.md, без Supabase
│   ├── tool-audit.md          ← обновлён (убран import_coeff_table)
│   ├── tool-localization.md   ← обновлён (Excel-fallback, --no-sheets)
│   ├── concepts.md            ← без изменений
│   ├── workflow-localization.md
│   ├── warehouses.md          ← без изменений
│   └── specs/
│       └── 2026-05-09-finalize-v1-design.md   ← этот документ
├── .env                       ← gitignored
├── .env.example               ← обновлён, без SUPABASE_*, с WB_TOOLKIT_DB_PATH
├── cabinets.yaml              ← формат без изменений; sheet_id может быть пустой
├── warehouse_status.yaml      ← без изменений
├── check_setup.py             ← обновлён: SQLite-чек вместо Supabase-чека
├── requirements.txt           ← без supabase>=2.4.0
└── README.md                  ← обновлён quickstart
```

Удаляется:
- `audit/etl/import_coeff_table.py`
- `shared/supabase.py`

---

## 3. Финальные артефакты, которые выдаёт инструмент

| # | Артефакт | Команда | Output |
|---|---|---|---|
| 1 | Аудит переплат | `python audit/run_audit.py <cab> <from> <to>` | `Аудит логистики YYYY-MM-DD — YYYY-MM-DD.xlsx` (12 листов) |
| 2 | Локализация Phase 1 — анализ ИЛ/ИРП | `python localization/run_analysis.py <cab> --days N` | JSON-кэш + Sheets/Excel «Анализ ИЛ/ИРП» |
| 3 | Локализация Phase 2 — 13-нед. roadmap | `python localization/run_roadmap.py <cab> --target 85` | Sheets/Excel «Roadmap» |
| 4 | Локализация Phase 3 — перестановки | `python localization/run_permutations.py <cab>` | Sheets/Excel «Перестановки» |

Phase 2/3 читают cache от Phase 1 — Phase 1 нужно прогнать первой; дальше 2/3 запускаются без повторного download отчёта.

---

## 4. Onboarding нового кабинета

```
1. WB Partners → Настройки → API → создать токен
   Категории: Статистика, Контент, Аналитика, Тарифы (все четыре)
2. cabinets.yaml — добавить:
   - name: <name>
     sheet_id: ""           # пусто = Excel-fallback
3. .env — добавить:
   WB_TOKEN_<NAME_UPPER>=eyJ...
4. python check_setup.py    # ожидаем 6/6 зелёных
5. ssh timeweb && python audit/run_audit.py <name> <from> <to>
```

`check_setup.py` после Фазы А проверяет:

| # | Проверка |
|---|---|
| 1 | `.env` существует |
| 2 | `credentials.json` не закоммичен |
| 3 | `cabinets.yaml` валиден |
| 4 | `warehouse_status.yaml` существует |
| 5 | для каждого кабинета из YAML есть `WB_TOKEN_<NAME>` |
| 6 | `data/wb_toolkit.db` существует, есть тарифы за последние 7 дней |

Без Supabase. `credentials.json` — **не обязателен**, нужен только для Sheets-вывода.

---

## 5. Поэтапный план работ (6 фаз, ~3 рабочих дня)

### Фаза А — SQLite-миграция (0.5 дня)

- `shared/db.py` (новый): тонкий sqlite3 wrapper, при первом подключении выставляет `PRAGMA journal_mode=WAL`, создаёт таблицу `wb_tariffs(warehouse_name TEXT, dt DATE, delivery_coef_pct NUMERIC, box_delivery_base NUMERIC, box_delivery_liter NUMERIC, created_at TIMESTAMP, PRIMARY KEY (warehouse_name, dt))`.
- `shared/coeff_table.py` — оставляем константу `COEFF_TABLE`, удаляем загрузку из БД.
- `audit/etl/tariff_collector.py` — `INSERT ... ON CONFLICT(warehouse_name, dt) DO UPDATE SET ...`.
- `audit/calculators/warehouse_coef_resolver.py` — `SELECT ... FROM wb_tariffs WHERE ...` через sqlite3.
- `scripts/migrate_supabase_to_sqlite.py` — выкачивает текущие 61 склад × 60 дней из Supabase, заливает в новый SQLite-файл. Запускается один раз, после прогона — удаляется коммитом.
- Удаляем `audit/etl/import_coeff_table.py`, `shared/supabase.py`.
- Убираем `supabase>=2.4.0` из `requirements.txt`.
- `check_setup.py` — заменяем чек Supabase на SQLite-чек (существование файла + строки за 7 дней).
- Обновляем тесты (мокаем `shared.db.get_connection` вместо `shared.supabase.get_supabase_client`).
- **Зависимости:** —
- **Коммит:** `feat(db): replace Supabase with local SQLite storage`

### Фаза Б — Excel-writer + единый Sheets-конфиг (0.5 дня)

- `localization/output/writer.py` — `Writer` Protocol, два импла:
  - `SheetsWriter` — рефакторинг текущего кода из `localization/sheets/*`.
  - `ExcelWriter` — новый, на openpyxl. Поддерживает несколько листов в одном файле.
- В Phase 1/2/3 раннерах:
  - выбор писателя по правилу из §1.2.
  - флаг `--no-sheets` форсирует Excel.
- Унификация: везде в коде `os.environ["GOOGLE_CREDENTIALS_PATH"]` (убираем `GOOGLE_CREDENTIALS_JSON`).
- Unit-тесты для `ExcelWriter`: несколько листов, корректные заголовки, пустые данные не падают.
- **Зависимости:** —
- **Коммит:** `refactor(localization): Excel-fallback writer + unify GOOGLE_CREDENTIALS_PATH`

### Фаза В — E2E проверка Phase 2 и Phase 3 локализации (0.5 дня)

- Прогон `python localization/run_roadmap.py ooo --target 85` на живом WB API.
- Прогон `python localization/run_permutations.py ooo`.
- Если вылезут API-изменения (как было с `warehouse_remains` или `cards/list`) — чиним по образцу предыдущих фиксов.
- Добавляем интеграционные тесты `tests/localization/test_run_roadmap.py` и `test_run_permutations.py` с моками внешних вызовов (по образцу `tests/audit/test_run_audit.py`).
- **Зависимости:** Б (нужен ExcelWriter для проверки fallback)
- **Коммит:** `fix(localization): Phase 2/3 verified on live WB API + integration tests`

### Фаза Г — Cron на app server + мониторинг (0.5 дня)

1. SSH `timeweb` → `git clone /opt/wb-logistics-toolkit`, venv, pip install.
2. Создаём `.env` на сервере (perms 600, владелец — пользователь cron).
3. Запускаем разово `scripts/migrate_supabase_to_sqlite.py` → создаётся `data/wb_toolkit.db`.
4. `deploy/cron_wrapper.sh` — обёртка:
   - redirect в `/var/log/wb-toolkit/<task>.log`
   - при exit ≠ 0 → POST в Telegram bot API через `TELEGRAM_ALERTS_BOT_TOKEN`
5. `deploy/crontab` (документ + установка через `crontab -e`):
   - `0 6 * * * /opt/wb-logistics-toolkit/deploy/cron_wrapper.sh tariff-ooo .venv/bin/python audit/etl/tariff_collector.py --cabinet ooo`
   - `5 6 * * * /opt/wb-logistics-toolkit/deploy/cron_wrapper.sh tariff-ip .venv/bin/python audit/etl/tariff_collector.py --cabinet ip`
   - `0 2 * * 0 /opt/wb-logistics-toolkit/deploy/backup.sh` (см. ниже)

   `deploy/backup.sh`:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   DEST=/var/backups/wb_toolkit
   mkdir -p "$DEST"
   cp /opt/wb-logistics-toolkit/data/wb_toolkit.db "$DEST/wb_toolkit-$(date +%F).db"
   find "$DEST" -name 'wb_toolkit-*.db' -mtime +56 -delete
   ```
6. `deploy/logrotate.conf` → `/etc/logrotate.d/wb-toolkit` (sudo) — daily, keep 14, compress.
7. Проверка: forced-run wrapper'а с заведомо невалидным токеном → exit ≠ 0, в Telegram приходит сообщение.
8. Документ `docs/deploy.md` — пошаговая инструкция переустановки с нуля.
- **Зависимости:** А
- **Коммит:** `chore(deploy): cron + alerts + backup on app server`

### Фаза Д — Smoke-тест на кабинете ИП (0.5 дня)

- `WB_TOKEN_IP` в `.env` (на сервере и локально).
- `cabinets.yaml` — добавить блок ИП.
- `python check_setup.py` → 6/6 зелёных для ИП.
- Прогон всех 4 артефактов для ИП:
  1. `python audit/run_audit.py ip 2026-02-01 2026-04-30`
  2. `python localization/run_analysis.py ip --days 60`
  3. `python localization/run_roadmap.py ip --target 85`
  4. `python localization/run_permutations.py ip`
- Открываем 4 файла глазами, проверяем разумность чисел: переплата % в диапазоне 3-7%, ИЛ% и loc_pct непустые, roadmap содержит 13 недель, перестановки — конкретные движения.
- Любой выявленный баг чиним atomic-коммитом.
- **Зависимости:** А, Б, В, Г
- **Коммит:** `test(cabinets): IP cabinet end-to-end smoke verified`

### Фаза Е — Документация и cleanup (0.5 дня)

- `docs/setup.md` — переписан без Supabase, scope WB-токена расширен до 4 категорий.
- `docs/tariffs-db.md` → `docs/tariffs-storage.md`, раздел про SQLite, как backfill.
- `docs/tool-audit.md` — убрать упоминания `import_coeff_table.py`.
- `docs/tool-localization.md` — добавить Excel-fallback и `--no-sheets`.
- `docs/onboarding-cabinet.md` — новый файл, детальная версия §4 этого спека.
- `docs/deploy.md` — уже создан в Фазе Г, проверяется на актуальность.
- `docs/index.md` — навигация (создаётся, если нет).
- `README.md` — quickstart обновлён.
- `.env.example` — обновлён, без `SUPABASE_*`, с `WB_TOOLKIT_DB_PATH`.
- Удаление `scripts/migrate_supabase_to_sqlite.py` (одноразовый).
- Финальный прогон `pytest -q` → 0 failed.
- **Зависимости:** А, Б, В, Г, Д
- **Коммит:** `docs: rewrite setup, deploy, onboarding; remove Supabase mentions`

### Финал

- Ветка `feat/finalize-v1` — мерджится в `main` одним PR.
- PR-описание ссылается на этот спек-документ.
- CI зелёный.

---

## 6. Acceptance Criteria

«Готово» = все 30 критериев выполнены.

### Код и тесты

| # | Критерий |
|---|---|
| 1 | `pytest tests/ -q` → ≥ 145 passed, 0 failed |
| 2 | `grep -rE "supabase\|SUPABASE_" --include="*.py" .` (после удаления migrate-скрипта) → пусто |
| 3 | `grep supabase requirements.txt` → пусто |
| 4 | `tests/localization/test_run_roadmap.py` и `test_run_permutations.py` существуют, с моками |
| 5 | Тесты `ExcelWriter`: «несколько листов в одном файле», «корректные заголовки», «пустые данные не падают» |

### Onboarding и конфигурация

| # | Критерий |
|---|---|
| 6 | `check_setup.py` 6/6 зелёных на свежей установке (если БД нет — создаёт автоматически и предлагает запустить collector) |
| 7 | Из пустого `.env` + `cabinets.yaml` (только OOO) до первого Excel — ≤ 4 шага по `docs/onboarding-cabinet.md` |
| 8 | `cabinets.yaml` со `sheet_id: ""` не падает, делает Excel-fallback |
| 9 | `cabinets.yaml` с валидным `sheet_id` пишет в Sheets |

### E2E на двух кабинетах

| # | Критерий |
|---|---|
| 10 | Аудит OOO: exit 0, Excel 12 листов, лист 9 ≥ 200 SKU, СВОД заполнен, переплата 3-7 % |
| 11 | Аудит ИП: то же |
| 12 | Phase 1 OOO: JSON-кэш, ИЛ% и loc_pct посчитаны, файл с per-article таблицей |
| 13 | Phase 1 ИП: то же |
| 14 | Phase 2 OOO: 13 недель, прогноз loc% по артикулам |
| 15 | Phase 2 ИП: то же |
| 16 | Phase 3 OOO: конкретные движения «откуда → куда → штук» |
| 17 | Phase 3 ИП: то же |

Итого 8 артефактов (4 × 2 кабинета) лежат в `output/` или Sheets, открыты глазами.

### Сервер и cron

| # | Критерий |
|---|---|
| 18 | `/opt/wb-logistics-toolkit/` существует, venv установлен, импорты проходят |
| 19 | `data/wb_toolkit.db` мигрирован: `SELECT count(*) FROM wb_tariffs` ≥ 60 |
| 20 | SQLite в WAL: `PRAGMA journal_mode` → `wal` |
| 21 | `crontab -l` содержит 3 строки (collector OOO + collector ИП + backup) |
| 22 | Принудительный запуск collector через wrapper → exit 0, новая строка в БД, лог появился, **никакого** Telegram-алерта |
| 23 | Принудительный запуск с битым токеном → exit ≠ 0, Telegram-сообщение пришло |
| 24 | `/var/backups/wb_toolkit/` содержит хотя бы один файл |
| 25 | `logrotate -d /etc/logrotate.d/wb-toolkit` → нет ошибок |

### Документация

| # | Критерий |
|---|---|
| 26 | `docs/onboarding-cabinet.md` существует, читается за < 5 минут |
| 27 | `docs/deploy.md` позволяет переустановить с нуля |
| 28 | `grep -i supabase docs/setup.md` → пусто |
| 29 | `README.md` quickstart соответствует текущему flow |
| 30 | `audit/etl/import_coeff_table.py` удалён |

### Не входит в acceptance (явно отложено в backlog v2)

- Кэш raw `reportDetailByPeriod`
- Web-интерфейс / API-обёртка
- Автоматизация перестановок Phase 3 через cron
- Postgres-миграция

Это явно помечено в `docs/index.md` как «v1 cap».

---

## 7. Риски и mitigations

| Риск | Вероятность | Mitigation |
|---|---|---|
| WB снова поменяет shape какого-то endpoint'а | средняя | в каждой Фазе E2E-прогон ловит, чиним atomic-коммитом — это уже отработанный паттерн |
| Токен ИП имеет урезанные scope'ы (например нет «Тарифы») | средняя | `check_setup.py` зажжёт ❌ — оператор перевыпускает токен с правильными правами |
| Потеря `data/wb_toolkit.db` на сервере | низкая | weekly backup в `/var/backups/wb_toolkit/`, ротация 8 копий |
| Cron-сборщик падает без алерта | низкая | wrapper-скрипт обязательно проверяет exit code и шлёт в Telegram |
| Phase 2/3 локализации не дают разумных результатов на ИП | средняя | в Фазе Д открываем глазами и сверяем; если нужно — корректируем калькуляторы |
| Concurrent чтение SQLite во время cron-записи | низкая | `PRAGMA journal_mode=WAL` |

---

## 8. Открытые вопросы (на момент финализации спека)

Нет.

Все архитектурные решения зафиксированы. Все compensating controls описаны. Реализация — детерминированная, без неизвестных.
