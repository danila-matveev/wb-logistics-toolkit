# WB Logistics Toolkit

Два инструмента для Wildberries-продавца, который хочет перестать переплачивать за логистику.

## Инструменты

### 1. Оптимизатор локализации
Показывает текущий Индекс Локализации (ИЛ), рассчитывает переплату из-за него и строит план перемещений товаров для снижения расходов.

### 2. Аудит переплат
Пересчитывает историческую логистику по официальным тарифам WB. Используется для выявления расхождений и возврата переплат.

## Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/your-org/wb-logistics-toolkit.git
cd wb-logistics-toolkit

# 2. Установить зависимости
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Настроить
cp .env.example .env
# Отредактировать .env и cabinets.yaml

# 4. Проверить настройку
python check_setup.py

# 5. Запустить анализ (появится в рамках Plan 2)
# python localization/run_analysis.py --cabinet ooo --days 90
```

## Документация

> **Примечание:** Документация создаётся в рамках Plan 4. Файлы появятся в директории `docs/`.

- [Установка](docs/setup.md) _(coming soon)_
- [Ключевые понятия](docs/concepts.md) _(coming soon)_
- [Как работать с инструментом](docs/workflow-localization.md) _(coming soon)_
- [Справочник складов](docs/warehouses.md) _(coming soon)_
- [Аудит переплат](docs/tool-audit.md) _(coming soon)_
- [Supabase и тарифы](docs/tariffs-db.md) _(coming soon)_

## Instrument 1: Localization Optimizer

Three-phase workflow for optimizing WB Индекс Локализации.

### Prerequisites

1. Supabase `wb_coeff_table` populated (see `audit/etl/import_coeff_table.py`)
2. `cabinets.yaml` — cabinet name, WB token env var, Google Sheet ID
3. `.env` — `WB_TOKEN_<CABINET>=...` and optionally `GOOGLE_CREDENTIALS_JSON=...`

### Phase 1 — ИЛ/ИРП Analysis

Fetches orders + report, computes per-article localization metrics and scenario economics.
Saves results to `localization/data/cache/<cabinet>_latest.json`.

```bash
python localization/run_analysis.py MAIN --days 30
```

### Phase 2 — 13-week Roadmap

Reads Phase 1 cache, generates movement plan, simulates weekly ИЛ improvement.

```bash
python localization/run_roadmap.py MAIN --target 85 --limit 0.3
```

### Phase 3 — Stock Permutations

Reads Phase 1 cache + live warehouse_remains, outputs per-article movement and supply recommendations.

```bash
python localization/run_permutations.py MAIN --safety-days 14
```

## Требования

- Python 3.11+
- WB API токен (из WB Partners)
- Google Service Account с доступом к Sheets
- Supabase проект (для истории тарифов и таблицы КТР/КРП)
