# Supabase — схема и ETL тарифов

Как устроено хранение исторических тарифов WB и как поддерживать базу актуальной.

---

## Зачем нужна база тарифов

WB меняет коэффициенты складов без уведомления. При аудите переплат за прошлый период нужно знать, какой тариф действовал на каждую конкретную дату. Если брать текущий тариф — расчёт будет неточным.

ETL собирает тарифы ежедневно и сохраняет историю. Аудит поднимает тариф для каждой строки по дате операции.

---

## Таблицы Supabase

### `wb_tariffs` — история коэффициентов складов

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | uuid | PK, auto |
| `warehouse_name` | text | Название склада (как в WB API) |
| `date` | date | Дата, на которую действует тариф |
| `delivery_coef_pct` | numeric | Коэффициент доставки % (например: 100, 150, 225) |
| `box_delivery_base` | numeric | Базовая ставка ₽/л |
| `box_delivery_liter` | numeric | Ставка за каждый доп. литр сверх базы |
| `created_at` | timestamptz | Дата загрузки в Supabase |

Ключ уникальности: `(warehouse_name, date)`. Повторный запуск ETL за ту же дату — upsert (не дублирует).

**Как аудит использует таблицу:**

`warehouse_coef_resolver` ищет запись с `warehouse_name = <склад>` и `date = <дата операции>`. Если точного совпадения нет — берётся ближайшая более ранняя дата (fill-forward).

### `wb_coeff_table` — таблица КТР/КРП

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | PK |
| `min_loc` | numeric | Минимальная ДЛ % (включительно) |
| `max_loc` | numeric | Максимальная ДЛ % (исключительно, кроме верхней границы) |
| `ktr` | numeric | Коэффициент транспортировки |
| `krp_pct` | numeric | КРП % от продажной цены |
| `valid_from` | date | Дата вступления в силу |

**Версионирование:** при изменении тарифной политики WB добавляется новая строка с `valid_from`. Старые строки не трогаются — аудит прошлых периодов использует правильный тариф для своей даты.

При старте `shared/coeff_table.py` выбирает актуальную версию:
```sql
SELECT * FROM wb_coeff_table
WHERE valid_from <= CURRENT_DATE
ORDER BY valid_from DESC
```

---

## Первоначальная настройка

### 1. Создать таблицы в Supabase

Откройте Supabase → SQL Editor и выполните:

```sql
-- История тарифов складов
CREATE TABLE wb_tariffs (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  warehouse_name text NOT NULL,
  date date NOT NULL,
  delivery_coef_pct numeric,
  box_delivery_base numeric,
  box_delivery_liter numeric,
  created_at timestamptz DEFAULT now(),
  UNIQUE(warehouse_name, date)
);

-- Таблица КТР/КРП
CREATE TABLE wb_coeff_table (
  id serial PRIMARY KEY,
  min_loc numeric NOT NULL,
  max_loc numeric NOT NULL,
  ktr numeric NOT NULL,
  krp_pct numeric NOT NULL,
  valid_from date NOT NULL
);
```

### 2. Загрузить начальную таблицу КТР/КРП

```bash
python audit/etl/import_coeff_table.py
```

Скрипт берёт данные из верифицированного справочника `irp_coefficients.py` и загружает в `wb_coeff_table` с `valid_from = 2024-01-01` (или первой известной датой).

### 3. Загрузить исторические тарифы складов

Для корректного аудита прошлых периодов нужно наполнить `wb_tariffs`. ETL собирает только текущий день — чтобы заполнить историю, запустите по диапазону дат:

```bash
# Заполнить конкретный день
python audit/etl/tariff_collector.py --date 2026-03-15

# Или запустите несколько раз для нужных дат
for date in 2026-01-01 2026-02-01 2026-03-01; do
    python audit/etl/tariff_collector.py --date $date
done
```

> При аудите за период без данных в Supabase — аудит использует fallback (`dlv_prc` из отчёта WB). Расчёт работает, но менее точен.

---

## ETL — ежедневный сбор тарифов

### Запуск вручную

```bash
# Сегодняшние тарифы
python audit/etl/tariff_collector.py

# За конкретную дату
python audit/etl/tariff_collector.py --date 2026-05-01

# Проверить дату последней загрузки
python audit/etl/tariff_collector.py --check
```

Скрипт:
1. Запрашивает `/api/v1/tariffs/box` из WB API
2. Upsert в `wb_tariffs` по ключу `(warehouse_name, date)`

### Настройка cron (рекомендуется)

На сервере (crontab или systemd timer):

```bash
# Каждый день в 08:00
0 8 * * * cd /path/to/wb-logistics-toolkit && .venv/bin/python audit/etl/tariff_collector.py >> logs/tariff_etl.log 2>&1
```

Или через Supabase Edge Functions / внешний cron-сервис (cron-job.org, GitHub Actions).

**GitHub Actions пример:**

```yaml
name: Tariff ETL
on:
  schedule:
    - cron: '0 5 * * *'   # 05:00 UTC = 08:00 MSK
jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt
      - run: python audit/etl/tariff_collector.py
        env:
          WB_TOKEN_OOO: ${{ secrets.WB_TOKEN_OOO }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
```

---

## Обновление таблицы КТР/КРП при изменении тарифов WB

Когда WB меняет тарифную политику (порядок раз в несколько месяцев):

1. Обновите справочник в `audit/etl/import_coeff_table.py`
2. Добавьте новые строки с `valid_from = <дата изменения>`

```python
# Пример: WB снизил КТР на верхнем диапазоне с 2026-06-01
new_rows = [
    {"min_loc": 95, "max_loc": 100, "ktr": 0.45, "krp_pct": 0, "valid_from": "2026-06-01"},
    # остальные диапазоны если изменились...
]
```

3. Запустите импорт с флагом `--append`:

```bash
python audit/etl/import_coeff_table.py --append
```

**Не удаляйте старые строки.** Аудит за периоды до изменения должен использовать старые коэффициенты.

---

## Мониторинг актуальности

`run_audit.py` при запуске проверяет дату последней записи в `wb_tariffs`. Если данные старше 2 дней — выводит предупреждение. Аудит при этом всё равно запускается (с пониженной точностью для пропущенных дат).

Чтобы проверить вручную:

```bash
python audit/etl/tariff_collector.py --check
# Выводит: Last update: 2026-05-06 (1 day ago) — OK
# или:     Last update: 2026-05-01 (6 days ago) — WARNING: stale tariffs
```

---

## Безопасность

Supabase подключается через `anon key` (открытый ключ). RLS на таблицах рекомендуется настроить так, чтобы чтение было открытым, а запись — только через `service_role`:

```sql
-- Разрешить чтение anon
ALTER TABLE wb_tariffs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "read_all" ON wb_tariffs FOR SELECT USING (true);

-- Запись — только через service_role (ETL)
-- service_role ключ используется в tariff_collector.py
```

В `.env` держите `SUPABASE_KEY=<anon key>` для обычного использования и отдельно `SUPABASE_SERVICE_KEY=<service role key>` для ETL (если включили RLS на запись).
