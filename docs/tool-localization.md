# Технический гайд — Оптимизатор локализации

Для разработчиков: архитектура модулей, форматы данных, точки расширения.

---

## Архитектура

```
localization/
├── run_analysis.py          — точка входа Фазы 1
├── run_roadmap.py           — точка входа Фазы 2
├── run_permutations.py      — точка входа Фазы 3
├── permutation_calculator.py — алгоритм перестановок
├── calculators/
│   ├── il_irp_analyzer.py   — расчёт ДЛ/КТР/КРП по артикулам
│   ├── scenario_engine.py   — сценарный анализ 30–90%
│   ├── relocation_forecaster.py — 13-недельный прогноз
│   └── reference_builder.py — справочник для Sheets
├── sheets/                  — рендеринг листов Google Sheets
│   ├── analysis/
│   ├── roadmap/
│   ├── permutations/
│   ├── dashboard.py
│   └── formatters.py
└── data/
    ├── mappings.py          — склады → ФО, области → ФО
    ├── history.db           — SQLite история расчётов
    └── cache/               — JSON кэш между фазами
```

---

## shared/ — общий слой

### `shared/config.py`

Читает `cabinets.yaml` + `.env`. Два публичных объекта:

```python
from shared.config import get_cabinet, load_warehouse_statuses

cabinet = get_cabinet("ooo")          # Cabinet(name, wb_token, sheet_id)
warehouses = load_warehouse_statuses()  # dict[name, WarehouseStatus]
warehouses_active = load_warehouse_statuses(available_only=True)
```

`Cabinet` — frozen dataclass:
- `name: str` — имя из cabinets.yaml
- `wb_token: str` — токен из env (WB_TOKEN_{NAME})
- `sheet_id: str` — ID Google Sheets

`WarehouseStatus` — frozen dataclass:
- `name: str` — название склада (ключевое поле — совпадает с именем в API)
- `fd: str` — федеральный округ
- `available: bool` — включать ли в расчёты
- `redistribution_limit_per_day: int` — лимит перераспределения (шт/день)
- `reason: str` — причина закрытия (если available=false)
- `note: str` — произвольная заметка

### `shared/wb_api/client.py`

```python
from shared.wb_api.client import WBClient

client = WBClient(token=cabinet.wb_token)
```

Принимает токен напрямую. Все API-модули принимают `client` первым аргументом.

### `shared/wb_api/` — эндпоинты

| Модуль | Функция | WB API |
|--------|---------|--------|
| `orders.py` | `fetch_orders(client, days)` | supplier/orders |
| `reports.py` | `fetch_report(client, date_from, date_to)` | reportDetailByPeriod v5 |
| `tariffs.py` | `fetch_box_tariffs(client)` | /api/v1/tariffs/box |
| `content.py` | `fetch_nm_volumes(client, nm_ids)` | content/v2 |
| `warehouse_remains.py` | `fetch_warehouse_remains(client)` | warehouse-remains |

### `shared/coeff_table.py`

Загружает актуальную таблицу КТР/КРП из Supabase:

```python
from shared.coeff_table import load_coeff_table

table = load_coeff_table()   # list[CoeffRow]
```

`CoeffRow`:
- `min_loc`, `max_loc` — диапазон ДЛ %
- `ktr` — коэффициент транспортировки
- `krp_pct` — КРП в % от цены
- `valid_from` — дата вступления в силу

При старте выбирается строка с `max(valid_from) where valid_from <= today`.

---

## Модули calculators/

### `il_irp_analyzer.py`

Основной расчётный модуль. Принимает список заказов, возвращает DataFrame по артикулам.

**Входные данные:**
```python
orders: list[dict]   # из fetch_orders() — поля: article, warehouseName, regionName, date
coeff_table: list[CoeffRow]
```

**Выходные данные — по артикулу:**
- `dl_pct` — Доля Локализации %
- `ktr` — коэффициент по dl_pct из таблицы
- `krp_pct` — КРП % по dl_pct из таблицы
- `orders_total` — заказов всего
- `orders_by_fd` — dict ФО → кол-во заказов

**Маппинг склад → ФО:**
Читается из `localization/data/mappings.py`. При добавлении нового склада WB — добавить туда.

### `scenario_engine.py`

Строит сценарии «что было бы, если бы ДЛ была X%»:

```python
from localization.calculators.scenario_engine import build_scenarios

scenarios = build_scenarios(
    articles=analyzed_articles,    # список ArticleMetrics
    base_logistics_cost=500_000,   # фактические расходы в месяц
    scenarios=[30, 40, 50, 60, 70, 80, 90],
)
```

Возвращает список `ScenarioResult(target_dl, estimated_cost, savings)`.

Ограничение: сценарий применяет один КТР ко всем артикулам. Это упрощение — реальный эффект зависит от распределения артикулов.

### `relocation_forecaster.py`

Симулирует 13-недельную динамику ИЛ после предложенных перемещений:

```python
from localization.calculators.relocation_forecaster import simulate_13w

forecast = simulate_13w(
    current_dl_by_article=dict,     # артикул → текущий ДЛ%
    target_dl_by_article=dict,      # артикул → целевой ДЛ% после перемещения
    orders_by_article=dict,         # артикул → число заказов (вес)
)
# Возвращает list[WeekForecast(week, il_pct, ktr, has_irp)]
```

Формула инерции: `ДЛ_t = ((13-t) × ДЛ_до + t × ДЛ_после) / 13`

---

## `permutation_calculator.py`

Жадный алгоритм распределения остатков.

**Входные данные:**
- `warehouse_remains` — текущие остатки из WB API (артикул × склад → кол-во)
- `article_metrics` — ДЛ и заказы по ФО из кэша Фазы 1
- `warehouse_statuses` — из `warehouse_status.yaml`
- `safety_days` — мин. запас дней продаж на складе-доноре

**Алгоритм (упрощённо):**

1. Для каждого артикула вычисляет «вклад в проблему»: `(КТР_текущий - КТР_целевой) × заказы`
2. Сортирует артикулы по убыванию вклада
3. Для каждого артикула ищет лучший склад-получатель в нужном ФО
4. Вычисляет объём перемещения с учётом:
   - Лимит склада-получателя (`redistribution_limit_per_day × горизонт`)
   - Защита донора: не забирать если ДЛ донора упадёт ниже 70%
   - Запас безопасности (`safety_days`)

**Возвращает:**
- `relocations: list[Relocation(sku, from_warehouse, to_warehouse, qty, reason)]`
- `supply_needs: list[SupplyNeed(sku, target_fd, qty_needed)]`

---

## Кэш (localization/data/cache/)

Файл `{cabinet}_latest.json` содержит полный результат Фазы 1:

```json
{
  "cabinet": "ooo",
  "computed_at": "2026-05-06T10:00:00",
  "days": 90,
  "summary": {
    "il_pct": 67.3,
    "irp_articles_count": 14,
    "total_orders": 12847
  },
  "articles": [
    {
      "article": "model-a",
      "dl_pct": 54.2,
      "ktr": 1.10,
      "krp_pct": 2.05,
      "orders_total": 340,
      "orders_by_fd": {"Центральный": 184, "Приволжский": 56, ...}
    }
  ]
}
```

Фазы 2 и 3 читают только `articles` из этого файла.

---

## Добавить новый кабинет

1. Добавить в `cabinets.yaml`:
```yaml
cabinets:
  - name: new_cab
    sheet_id: "1NewSheetId..."
```

2. Добавить в `.env`:
```bash
WB_TOKEN_NEW_CAB=eyJ...
```

3. Запустить:
```bash
python check_setup.py
python localization/run_analysis.py --cabinet new_cab
```

---

## Добавить новый склад WB

Новые склады появляются в API автоматически, но их нужно добавить в маппинг:

1. Запустите анализ — в логах появится предупреждение `Unknown warehouse: <name>`
2. Найдите ФО по имени склада
3. Добавьте в `localization/data/mappings.py` в словарь `WAREHOUSE_TO_FD`
4. Добавьте в `warehouse_status.yaml` с `available: true` и лимитом из WB Partners

---

## Расширение алгоритма перестановок

Алгоритм в `permutation_calculator.py` — жадный (greedy). Точки расширения:

- **Приоритизация:** изменить функцию `_article_priority_score()` — сейчас это `(ktr - target_ktr) × orders`
- **Защита донора:** изменить порог 70% в константе `DONOR_MIN_DL_PCT`
- **Горизонт лимитов:** сейчас считается на `redistribution_limit_per_day × 30` дней
- **Сезонность:** `weekly_orders_history` зарезервирован в forecaster, пока не используется

---

## Форматы данных WB API

**`supplier/orders` (fetch_orders):**
```json
{
  "article": "model-a/white",
  "warehouseName": "Коледино",
  "regionName": "Московская область",
  "date": "2026-04-15",
  "isCancel": false
}
```

**`warehouse-remains` (fetch_warehouse_remains):**
```json
{
  "article": "model-a/white",
  "warehouseName": "Коледино",
  "quantity": 42
}
```

Имена складов в API могут иметь несколько вариантов написания для одного физического склада. Пример: Шушары в `warehouse_status.yaml` прописаны тремя строками — именно столько вариантов возвращает API в разных эндпоинтах.
