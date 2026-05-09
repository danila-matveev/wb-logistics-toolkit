# Phase А: SQLite Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить Supabase-зависимость на локальный SQLite-файл `data/wb_toolkit.db` (для `wb_tariffs`) и embedded Python-литерал (для `wb_coeff_table`), без изменения публичного поведения CLI и Excel-выхода.

**Architecture:** Тонкий sqlite3 wrapper в `shared/db.py` (singleton соединение с `PRAGMA journal_mode=WAL`). KTR/KRP справочник — константа в коде, потому что меняется ~раз в год. Историю тарифов читаем по `(dt, warehouse_name)` через прямой SQL. Migration-script одноразовый, переносит текущие данные из Supabase в SQLite, после прогона удаляется.

**Tech Stack:** Python 3.11+, stdlib `sqlite3`, pytest, pytest-mock. Удаляется `supabase>=2.4.0`.

**Spec:** [docs/specs/2026-05-09-finalize-v1-design.md](../specs/2026-05-09-finalize-v1-design.md) §1.1, §1.5, §5 Фаза А.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `shared/db.py` | Create | sqlite3 connection singleton с WAL и DDL для `wb_tariffs` |
| `shared/coeff_table.py` | Modify | заменить `_load_from_supabase()` на embedded `COEFF_TABLE` константу |
| `shared/supabase.py` | Delete | больше не нужен |
| `audit/calculators/warehouse_coef_resolver.py` | Modify | переименовать `load_supabase_tariffs()` → `load_tariffs()`, читать из SQLite |
| `audit/etl/tariff_collector.py` | Modify | INSERT в SQLite вместо Supabase |
| `audit/etl/import_coeff_table.py` | Delete | bootstrap-скрипт больше не нужен (константа embedded) |
| `audit/run_audit.py` | Modify | вызов `load_tariffs()` вместо `load_supabase_tariffs()` |
| `check_setup.py` | Modify | `check_supabase()` → `check_sqlite()` |
| `scripts/migrate_supabase_to_sqlite.py` | Create | одноразовый migration-скрипт |
| `requirements.txt` | Modify | убрать `supabase>=2.4.0` |
| `.env.example` | Modify | убрать `SUPABASE_*`, добавить `WB_TOOLKIT_DB_PATH` |
| `.gitignore` | Verify | `*.db` уже есть, `data/` создаётся автоматически |
| `tests/shared/test_db.py` | Create | unit-тесты для `shared/db.py` |
| `tests/shared/test_coeff_table.py` | Modify | убрать supabase-моки, тестировать константу |
| `tests/audit/test_etl.py` | Modify | патч `shared.db.get_connection` |
| `tests/audit/test_run_audit.py` | Modify | патч `audit.run_audit.load_tariffs` |
| `tests/audit/test_warehouse_coef_resolver.py` | Modify | проверить новое имя функции |
| `tests/test_check_setup.py` | Modify | заменить `check_supabase` тесты на `check_sqlite` |

**Не трогаем в этой фазе:**
- `localization/*` — Phase Б отдельным планом
- `shared/sheets_client.py` — `GOOGLE_CREDENTIALS_JSON` остаётся до Фазы Б

---

## Branch Setup

- [ ] **Step 0.1: Создать ветку и убедиться что main чистый**

```bash
cd ~/Projects/wb-logistics-toolkit
git status                                    # ожидаем clean working tree
git checkout -b feat/phase-a-sqlite
```

Expected: переключились на новую ветку, working tree чистый.

- [ ] **Step 0.2: Прогнать существующие тесты — baseline**

```bash
pytest -q
```

Expected: 145+ passed, 0 failed. Это наш baseline; в конце плана должно быть столько же или больше.

---

## Task 1: shared/db.py — sqlite3 wrapper

**Files:**
- Create: `shared/db.py`
- Test: `tests/shared/test_db.py`

- [ ] **Step 1.1: Написать failing-тест на DDL и WAL**

Создать `tests/shared/test_db.py`:

```python
# tests/shared/test_db.py
import sqlite3
from pathlib import Path

import pytest

from shared import db as db_module


@pytest.fixture(autouse=True)
def reset_singleton(monkeypatch, tmp_path):
    """Force a fresh DB path and clear cached connection between tests."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    db_module._reset_for_tests()
    yield
    db_module._reset_for_tests()


def test_get_connection_creates_db_file(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    db_module._reset_for_tests()
    conn = db_module.get_connection()
    assert db_path.exists()
    assert isinstance(conn, sqlite3.Connection)


def test_get_connection_creates_wb_tariffs_table():
    conn = db_module.get_connection()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='wb_tariffs'"
    )
    assert cur.fetchone() is not None


def test_wb_tariffs_columns_match_spec():
    conn = db_module.get_connection()
    cur = conn.execute("PRAGMA table_info(wb_tariffs)")
    cols = {row[1]: row[2] for row in cur.fetchall()}
    assert cols == {
        "dt": "TEXT",
        "warehouse_name": "TEXT",
        "delivery_coef": "REAL",
        "logistics_1l": "REAL",
        "logistics_extra_l": "REAL",
        "box_storage_base": "REAL",
        "storage_coef": "REAL",
        "geo_name": "TEXT",
        "created_at": "TEXT",
    }


def test_wb_tariffs_primary_key_is_dt_warehouse():
    conn = db_module.get_connection()
    cur = conn.execute("PRAGMA table_info(wb_tariffs)")
    pk_cols = [row[1] for row in cur.fetchall() if row[5] > 0]
    pk_cols_sorted_by_pk_index = sorted(
        [(row[1], row[5]) for row in conn.execute("PRAGMA table_info(wb_tariffs)") if row[5] > 0],
        key=lambda x: x[1],
    )
    assert [c for c, _ in pk_cols_sorted_by_pk_index] == ["dt", "warehouse_name"]


def test_journal_mode_is_wal():
    conn = db_module.get_connection()
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_get_connection_returns_same_instance():
    conn1 = db_module.get_connection()
    conn2 = db_module.get_connection()
    assert conn1 is conn2


def test_default_path_when_env_var_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WB_TOOLKIT_DB_PATH", raising=False)
    db_module._reset_for_tests()
    db_module.get_connection()
    assert (tmp_path / "data" / "wb_toolkit.db").exists()
```

- [ ] **Step 1.2: Прогнать тест — должен упасть**

```bash
pytest tests/shared/test_db.py -v
```

Expected: ImportError или ModuleNotFoundError на `shared.db` — модуль ещё не создан.

- [ ] **Step 1.3: Реализовать shared/db.py**

```python
# shared/db.py
"""Local SQLite storage for wb-logistics-toolkit.

Replaces the prior Supabase-based storage. One writer (cron tariff collector),
N readers (audit/run_audit). WAL mode keeps readers unblocked during writes.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

_DEFAULT_PATH = "data/wb_toolkit.db"

_DDL = """
CREATE TABLE IF NOT EXISTS wb_tariffs (
    dt                TEXT NOT NULL,
    warehouse_name    TEXT NOT NULL,
    delivery_coef     REAL,
    logistics_1l      REAL,
    logistics_extra_l REAL,
    box_storage_base  REAL,
    storage_coef      REAL,
    geo_name          TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (dt, warehouse_name)
);
"""

_conn: sqlite3.Connection | None = None
_conn_lock = threading.Lock()


def _resolve_path() -> Path:
    raw = os.environ.get("WB_TOOLKIT_DB_PATH") or _DEFAULT_PATH
    return Path(raw)


def get_connection() -> sqlite3.Connection:
    """Return a process-wide SQLite connection, initialising WAL + schema once.

    Path is taken from `WB_TOOLKIT_DB_PATH` env var, defaulting to
    `data/wb_toolkit.db` relative to the current working directory.
    """
    global _conn
    if _conn is not None:
        return _conn
    with _conn_lock:
        if _conn is not None:
            return _conn
        path = _resolve_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_DDL)
        conn.commit()
        _conn = conn
    return _conn


def _reset_for_tests() -> None:
    """Drop the cached connection. ONLY for tests."""
    global _conn
    with _conn_lock:
        if _conn is not None:
            _conn.close()
        _conn = None
```

- [ ] **Step 1.4: Прогнать тест — должен пройти**

```bash
pytest tests/shared/test_db.py -v
```

Expected: 7 passed.

- [ ] **Step 1.5: Коммит**

```bash
git add shared/db.py tests/shared/test_db.py
git commit -m "feat(db): add SQLite wrapper with WAL and wb_tariffs schema"
```

---

## Task 2: shared/coeff_table.py — embedded constant

**Files:**
- Modify: `shared/coeff_table.py`
- Modify: `tests/shared/test_coeff_table.py`

- [ ] **Step 2.1: Переписать тесты под embedded-литерал**

Полностью заменить `tests/shared/test_coeff_table.py` на:

```python
# tests/shared/test_coeff_table.py
"""Tests for shared.coeff_table after Supabase removal — table is embedded."""
import pytest

from shared.coeff_table import COEFF_TABLE, get_ktr_krp, get_coeff_table, calc_financial_impact


def test_table_has_20_rows():
    assert len(COEFF_TABLE) == 20


def test_table_covers_full_0_100_range():
    sorted_rows = sorted(COEFF_TABLE, key=lambda r: r["min_loc"])
    assert sorted_rows[0]["min_loc"] == 0.0
    assert sorted_rows[-1]["max_loc"] == 100.0
    for prev, nxt in zip(sorted_rows, sorted_rows[1:]):
        assert nxt["min_loc"] > prev["max_loc"]
        assert nxt["min_loc"] - prev["max_loc"] < 0.02


def test_get_ktr_krp_high_localization():
    ktr, krp = get_ktr_krp(97.0)
    assert ktr == 0.50
    assert krp == 0.0


def test_get_ktr_krp_at_80_percent():
    ktr, krp = get_ktr_krp(82.0)
    assert ktr == 0.80
    assert krp == 0.0


def test_get_ktr_krp_at_irp_zone():
    ktr, krp = get_ktr_krp(57.0)
    assert ktr == 1.05
    assert krp == 2.00


def test_get_ktr_krp_zero_localization():
    ktr, krp = get_ktr_krp(0.0)
    assert ktr == 2.20
    assert krp == 2.50


def test_clamp_above_100():
    ktr, _ = get_ktr_krp(150.0)
    assert ktr == 0.50


def test_clamp_below_0():
    ktr, _ = get_ktr_krp(-10.0)
    assert ktr == 2.20


def test_get_coeff_table_returns_same_data():
    table = get_coeff_table()
    assert table is COEFF_TABLE


def test_calc_financial_impact_zero_inputs():
    assert calc_financial_impact(2.0, 0, 10, 30) == 0.0
    assert calc_financial_impact(2.0, 100, 0, 30) == 0.0


def test_calc_financial_impact_typical():
    impact = calc_financial_impact(krp_pct=2.0, price=1000.0, orders=300, period_days=30)
    assert impact == pytest.approx(2.0 / 100 * 1000 * 300, rel=1e-6)
```

- [ ] **Step 2.2: Прогнать — должен упасть на импорте `COEFF_TABLE`**

```bash
pytest tests/shared/test_coeff_table.py -v
```

Expected: ImportError на `from shared.coeff_table import COEFF_TABLE`.

- [ ] **Step 2.3: Переписать `shared/coeff_table.py` с embedded константой**

Полностью заменить файл:

```python
# shared/coeff_table.py
"""KTR/KRP coefficient table — embedded constant, source: WB Partners → Тарифы.

Effective from 2026-03-27. Update by editing COEFF_TABLE below + bumping the
"effective from" comment. No external storage; the table changes ~once a year.
"""
from __future__ import annotations

import warnings
from typing import Any

# KTR/KRP table effective from 27.03.2026 (source: WB Partners → Тарифы).
COEFF_TABLE: list[dict[str, Any]] = [
    {"min_loc": 95.00, "max_loc": 100.00, "ktr": 0.50, "krp_pct": 0.00},
    {"min_loc": 90.00, "max_loc":  94.99, "ktr": 0.60, "krp_pct": 0.00},
    {"min_loc": 85.00, "max_loc":  89.99, "ktr": 0.70, "krp_pct": 0.00},
    {"min_loc": 80.00, "max_loc":  84.99, "ktr": 0.80, "krp_pct": 0.00},
    {"min_loc": 75.00, "max_loc":  79.99, "ktr": 0.90, "krp_pct": 0.00},
    {"min_loc": 70.00, "max_loc":  74.99, "ktr": 1.00, "krp_pct": 0.00},
    {"min_loc": 65.00, "max_loc":  69.99, "ktr": 1.00, "krp_pct": 0.00},
    {"min_loc": 60.00, "max_loc":  64.99, "ktr": 1.00, "krp_pct": 0.00},
    {"min_loc": 55.00, "max_loc":  59.99, "ktr": 1.05, "krp_pct": 2.00},
    {"min_loc": 50.00, "max_loc":  54.99, "ktr": 1.10, "krp_pct": 2.05},
    {"min_loc": 45.00, "max_loc":  49.99, "ktr": 1.20, "krp_pct": 2.05},
    {"min_loc": 40.00, "max_loc":  44.99, "ktr": 1.30, "krp_pct": 2.10},
    {"min_loc": 35.00, "max_loc":  39.99, "ktr": 1.40, "krp_pct": 2.10},
    {"min_loc": 30.00, "max_loc":  34.99, "ktr": 1.60, "krp_pct": 2.15},
    {"min_loc": 25.00, "max_loc":  29.99, "ktr": 1.70, "krp_pct": 2.20},
    {"min_loc": 20.00, "max_loc":  24.99, "ktr": 1.80, "krp_pct": 2.25},
    {"min_loc": 15.00, "max_loc":  19.99, "ktr": 1.90, "krp_pct": 2.30},
    {"min_loc": 10.00, "max_loc":  14.99, "ktr": 2.00, "krp_pct": 2.35},
    {"min_loc":  5.00, "max_loc":   9.99, "ktr": 2.10, "krp_pct": 2.45},
    {"min_loc":  0.00, "max_loc":   4.99, "ktr": 2.20, "krp_pct": 2.50},
]


def get_ktr_krp(localization_pct: float) -> tuple[float, float]:
    """Return (КТР, КРП%) for a given per-article localization percentage."""
    loc = max(0.0, min(100.0, localization_pct))
    for row in COEFF_TABLE:
        if row["min_loc"] <= loc <= row["max_loc"]:
            return float(row["ktr"]), float(row["krp_pct"])
    warnings.warn(
        f"No coefficient row found for localization_pct={localization_pct:.2f} "
        f"(clamped={loc:.2f}). Using fallback (2.20, 2.50).",
        RuntimeWarning,
        stacklevel=2,
    )
    return 2.20, 2.50


def get_coeff_table() -> list[dict[str, Any]]:
    """Return the full coefficient table (read-only reference)."""
    return COEFF_TABLE


def calc_financial_impact(
    krp_pct: float,
    price: float,
    orders: int,
    period_days: int,
) -> float:
    """Monthly ИРП financial impact in ₽."""
    if krp_pct <= 0 or price <= 0 or orders <= 0 or period_days <= 0:
        return 0.0
    daily_orders = orders / period_days
    monthly_orders = daily_orders * 30
    return krp_pct / 100.0 * price * monthly_orders
```

Удаляем функцию `clear_cache()` — она больше не нужна, кэша нет.

- [ ] **Step 2.4: Прогнать — должно пройти**

```bash
pytest tests/shared/test_coeff_table.py -v
```

Expected: 11 passed.

- [ ] **Step 2.5: Проверить, что никто не зовёт `clear_cache()`**

```bash
grep -rn "clear_cache" --include="*.py" . | grep -v __pycache__ | grep -v .venv
```

Expected: пусто (или только тест-файлы локализации, не зовущие `coeff_table.clear_cache`). Если найдёт — удалить вызовы.

- [ ] **Step 2.6: Прогнать локализационные тесты, которые extend coeff_table**

```bash
pytest tests/localization/test_coeff_table_extensions.py -v
```

Expected: passed. Если упадёт — посмотреть, что там зовётся, и адаптировать (минимально).

- [ ] **Step 2.7: Коммит**

```bash
git add shared/coeff_table.py tests/shared/test_coeff_table.py
git commit -m "refactor(coeff_table): embed COEFF_TABLE as Python literal"
```

---

## Task 3: warehouse_coef_resolver — переименование + SQLite

**Files:**
- Modify: `audit/calculators/warehouse_coef_resolver.py`
- Modify: `tests/audit/test_warehouse_coef_resolver.py` (если затрагивает имя)

- [ ] **Step 3.1: Узнать, что в текущих тестах**

```bash
grep -n "load_supabase_tariffs\|load_tariffs\|supabase" tests/audit/test_warehouse_coef_resolver.py
```

Если функция упоминается в тестах — переименовать там тоже на Step 3.4.

- [ ] **Step 3.2: Написать новый тест на `load_tariffs()`**

Добавить в `tests/audit/test_warehouse_coef_resolver.py`:

```python
import sqlite3
from datetime import date

from audit.calculators.warehouse_coef_resolver import load_tariffs


def test_load_tariffs_reads_from_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    from shared import db as db_module
    db_module._reset_for_tests()

    conn = db_module.get_connection()
    conn.executemany(
        "INSERT INTO wb_tariffs (dt, warehouse_name, delivery_coef) VALUES (?, ?, ?)",
        [
            ("2026-04-01", "Коледино", 95.0),
            ("2026-04-15", "Коледино", 100.0),
            ("2026-04-10", "Электросталь", 110.0),
            ("2026-03-01", "OutOfRange", 90.0),
        ],
    )
    conn.commit()

    result = load_tariffs(date(2026, 4, 1), date(2026, 4, 30))

    assert "Коледино" in result
    assert result["Коледино"][date(2026, 4, 1)] == 0.95
    assert result["Коледино"][date(2026, 4, 15)] == 1.00
    assert result["Электросталь"][date(2026, 4, 10)] == 1.10
    assert "OutOfRange" not in result

    db_module._reset_for_tests()


def test_load_tariffs_empty_db_returns_empty(tmp_path, monkeypatch):
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    from shared import db as db_module
    db_module._reset_for_tests()
    result = load_tariffs(date(2026, 1, 1), date(2026, 12, 31))
    assert result == {}
    db_module._reset_for_tests()
```

- [ ] **Step 3.3: Прогнать — должно упасть на импорте `load_tariffs`**

```bash
pytest tests/audit/test_warehouse_coef_resolver.py -v
```

Expected: ImportError или AttributeError на `load_tariffs`.

- [ ] **Step 3.4: Переписать `audit/calculators/warehouse_coef_resolver.py`**

Заменить файл целиком:

```python
"""3-tier warehouse coefficient resolution: fixation → SQLite → dlv_prc."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from shared.db import get_connection

logger = logging.getLogger(__name__)


@dataclass
class CoefResult:
    value: float
    source: str   # "fixation" | "sqlite" | "dlv_prc"
    verified: bool  # False only for dlv_prc fallback


def resolve_warehouse_coef(
    dlv_prc: float,
    fixed_coef: float,
    fixation_end: date | None,
    order_date: date | None,
    warehouse_name: str,
    supabase_tariffs: dict[str, dict[date, float]],
) -> CoefResult:
    """Resolve warehouse coefficient with 3-tier priority.

    Priority:
    1. Fixed coefficient (if fixation is active: fixation_end > order_date)
    2. Historical tariffs from SQLite (param name kept for backwards compat)
    3. dlv_prc from report (fallback, not verified)

    The `supabase_tariffs` parameter name is preserved to avoid touching every
    call site in this PR; the data is still passed in the same shape.
    """
    if fixed_coef > 0 and fixation_end and order_date and fixation_end > order_date:
        return CoefResult(value=fixed_coef, source="fixation", verified=True)

    wh_tariffs = supabase_tariffs.get(warehouse_name)
    if wh_tariffs and order_date:
        matching_dates = [d for d in wh_tariffs if d <= order_date]
        if matching_dates:
            closest = max(matching_dates)
            coef = wh_tariffs[closest]
            if coef > 0:
                return CoefResult(value=coef, source="sqlite", verified=True)

    if dlv_prc > 0:
        return CoefResult(value=dlv_prc, source="dlv_prc", verified=False)

    return CoefResult(value=0.0, source="dlv_prc", verified=False)


def load_tariffs(date_from: date, date_to: date) -> dict[str, dict[date, float]]:
    """Load warehouse coefficients from SQLite wb_tariffs table.

    Returns:
        {warehouse_name: {date: delivery_coef / 100}}
    """
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT dt, warehouse_name, delivery_coef "
            "FROM wb_tariffs WHERE dt BETWEEN ? AND ?",
            (date_from.isoformat(), date_to.isoformat()),
        ).fetchall()
    except Exception as e:
        logger.warning("Failed to load tariffs from SQLite: %s", e)
        return {}

    result: dict[str, dict[date, float]] = {}
    for row in rows:
        coef_raw = row["delivery_coef"]
        if coef_raw is None:
            continue
        wh = row["warehouse_name"]
        dt = date.fromisoformat(row["dt"])
        coef = float(coef_raw) / 100.0
        if wh not in result:
            result[wh] = {}
        result[wh][dt] = coef
    logger.info("Loaded SQLite tariffs: %d warehouses", len(result))
    return result
```

> **Note:** `source` enum field теперь имеет значение `"sqlite"` вместо `"supabase"`. Если какой-то Excel-лист отображает это значение пользователю, его нужно проверить (см. Task 7 ниже).

- [ ] **Step 3.5: Прогнать новые тесты — должны пройти**

```bash
pytest tests/audit/test_warehouse_coef_resolver.py -v
```

Expected: все passed.

- [ ] **Step 3.6: Коммит**

```bash
git add audit/calculators/warehouse_coef_resolver.py tests/audit/test_warehouse_coef_resolver.py
git commit -m "refactor(audit): rename load_supabase_tariffs to load_tariffs, read SQLite"
```

---

## Task 4: run_audit.py — обновить вызов и импорт

**Files:**
- Modify: `audit/run_audit.py`
- Modify: `tests/audit/test_run_audit.py`

- [ ] **Step 4.1: Поправить тест-патч**

В `tests/audit/test_run_audit.py` заменить строку:

```python
patch("audit.run_audit.load_supabase_tariffs", return_value={}), \
```

на:

```python
patch("audit.run_audit.load_tariffs", return_value={}), \
```

- [ ] **Step 4.2: Прогнать — должен упасть на импорте**

```bash
pytest tests/audit/test_run_audit.py -v
```

Expected: тест падает на `AttributeError: module 'audit.run_audit' has no attribute 'load_tariffs'`.

- [ ] **Step 4.3: Поправить импорт и вызов в `audit/run_audit.py`**

Заменить:

```python
from audit.calculators.warehouse_coef_resolver import resolve_warehouse_coef, load_supabase_tariffs
```

на:

```python
from audit.calculators.warehouse_coef_resolver import resolve_warehouse_coef, load_tariffs
```

Заменить:

```python
# Step 5: Load Supabase historical tariffs
logger.info("Loading Supabase tariffs...")
supabase_tariffs = load_supabase_tariffs(config.date_from, config.date_to)
```

на:

```python
# Step 5: Load historical tariffs from SQLite
logger.info("Loading historical tariffs...")
supabase_tariffs = load_tariffs(config.date_from, config.date_to)
```

> **Note:** Локальная переменная `supabase_tariffs` остаётся под старым именем — это передаваемый параметр в `resolve_warehouse_coef()`, переименование её каскадно затронуло бы `resolve_warehouse_coef()` сигнатуру; косметический рефакторинг — задача отдельного PR.

- [ ] **Step 4.4: Прогнать тест — должен пройти**

```bash
pytest tests/audit/test_run_audit.py -v
```

Expected: passed.

- [ ] **Step 4.5: Проверить, что никто больше не импортирует старое имя**

```bash
grep -rn "load_supabase_tariffs" --include="*.py" . | grep -v __pycache__ | grep -v .venv
```

Expected: пусто.

- [ ] **Step 4.6: Коммит**

```bash
git add audit/run_audit.py tests/audit/test_run_audit.py
git commit -m "refactor(audit): wire run_audit to load_tariffs"
```

---

## Task 5: tariff_collector.py — INSERT в SQLite

**Files:**
- Modify: `audit/etl/tariff_collector.py`
- Modify: `tests/audit/test_etl.py`

- [ ] **Step 5.1: Поправить тест `test_etl.py` — убрать импорт удаляемого модуля**

В `tests/audit/test_etl.py` строка:

```python
from audit.etl.import_coeff_table import COEFF_TABLE
```

→ удалить, и удалить тесты `test_coeff_table_has_20_rows` и `test_coeff_table_covers_full_range` (они дублируют покрытие из `tests/shared/test_coeff_table.py`).

Добавить в конец:

```python
def test_collect_tariffs_inserts_into_sqlite(tmp_path, monkeypatch):
    """Smoke: collect_tariffs() upserts rows into SQLite via INSERT ... ON CONFLICT."""
    db_path = tmp_path / "etl.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    from shared import db as db_module
    db_module._reset_for_tests()

    fake_raw = [
        {
            "warehouseName": "Коледино",
            "boxDeliveryBase": "46,0",
            "boxDeliveryLiter": "14,0",
            "boxDeliveryCoefExpr": "95",
            "boxStorageBase": "0",
            "boxStorageLiter": "0",
            "boxStorageCoefExpr": "0",
        }
    ]
    fake_cab = MagicMock()
    fake_cab.wb_token = "tok"

    with patch("audit.etl.tariff_collector.get_cabinet", return_value=fake_cab), \
         patch("audit.etl.tariff_collector.WBClient"), \
         patch("audit.etl.tariff_collector.fetch_box_tariffs", return_value=fake_raw):
        from audit.etl.tariff_collector import collect_tariffs
        count = collect_tariffs(date(2026, 5, 1), "ooo")

    assert count == 1
    conn = db_module.get_connection()
    rows = conn.execute("SELECT * FROM wb_tariffs").fetchall()
    assert len(rows) == 1
    assert rows[0]["warehouse_name"] == "Коледино"
    assert rows[0]["delivery_coef"] == 95.0
    assert rows[0]["dt"] == "2026-05-01"

    # Run again — should UPSERT, not duplicate
    with patch("audit.etl.tariff_collector.get_cabinet", return_value=fake_cab), \
         patch("audit.etl.tariff_collector.WBClient"), \
         patch("audit.etl.tariff_collector.fetch_box_tariffs", return_value=fake_raw):
        from audit.etl.tariff_collector import collect_tariffs
        collect_tariffs(date(2026, 5, 1), "ooo")
    rows = conn.execute("SELECT * FROM wb_tariffs").fetchall()
    assert len(rows) == 1

    db_module._reset_for_tests()
```

- [ ] **Step 5.2: Прогнать — должен упасть**

```bash
pytest tests/audit/test_etl.py -v
```

Expected: падает на импорте `audit.etl.import_coeff_table` и/или новом тесте.

- [ ] **Step 5.3: Переписать `audit/etl/tariff_collector.py`**

Заменить файл:

```python
"""Daily ETL: fetch WB box tariffs → upsert into local SQLite wb_tariffs.

Usage:
    python audit/etl/tariff_collector.py                    # today, ooo cabinet
    python audit/etl/tariff_collector.py --date 2026-03-20
    python audit/etl/tariff_collector.py --backfill 30
    python audit/etl/tariff_collector.py --cabinet ip
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.config import get_cabinet
from shared.db import get_connection
from shared.wb_api.client import WBClient
from shared.wb_api.tariffs import fetch_box_tariffs
from audit.models.tariff_snapshot import TariffSnapshot

logger = logging.getLogger(__name__)


def build_upsert_rows(dt: date, raw_tariffs: list[dict]) -> list[dict]:
    """Convert raw API tariff list to upsert dicts."""
    rows = []
    for d in raw_tariffs:
        snap = TariffSnapshot.from_api(d)
        rows.append({
            "dt": dt.isoformat(),
            "warehouse_name": snap.warehouse_name,
            "delivery_coef": snap.delivery_coef_pct,
            "logistics_1l": snap.box_delivery_base,
            "logistics_extra_l": snap.box_delivery_liter,
            "box_storage_base": snap.box_storage_base,
            "storage_coef": snap.storage_coef_pct,
            "geo_name": snap.geo_name,
        })
    return rows


_UPSERT_SQL = """
INSERT INTO wb_tariffs (
    dt, warehouse_name, delivery_coef, logistics_1l, logistics_extra_l,
    box_storage_base, storage_coef, geo_name
) VALUES (
    :dt, :warehouse_name, :delivery_coef, :logistics_1l, :logistics_extra_l,
    :box_storage_base, :storage_coef, :geo_name
)
ON CONFLICT(dt, warehouse_name) DO UPDATE SET
    delivery_coef     = excluded.delivery_coef,
    logistics_1l      = excluded.logistics_1l,
    logistics_extra_l = excluded.logistics_extra_l,
    box_storage_base  = excluded.box_storage_base,
    storage_coef      = excluded.storage_coef,
    geo_name          = excluded.geo_name,
    created_at        = datetime('now')
"""


def collect_tariffs(dt: date, cabinet_name: str) -> int:
    """Fetch tariffs for a single date and upsert into SQLite. Returns row count."""
    cab = get_cabinet(cabinet_name)
    client = WBClient(token=cab.wb_token)
    raw = fetch_box_tariffs(client, dt.isoformat())
    if not raw:
        logger.warning("No tariffs returned for %s", dt)
        return 0

    rows = build_upsert_rows(dt, raw)
    conn = get_connection()
    conn.executemany(_UPSERT_SQL, rows)
    conn.commit()
    logger.info("Upserted %d warehouse tariffs for %s", len(rows), dt)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="WB Tariff Collector → SQLite")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--backfill", type=int, default=None, help="Backfill last N days")
    parser.add_argument("--cabinet", type=str, default="ooo")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.backfill:
        total = 0
        for i in range(args.backfill):
            dt = date.today() - timedelta(days=i)
            total += collect_tariffs(dt, args.cabinet)
        logger.info("Backfill complete: %d total rows across %d days", total, args.backfill)
    else:
        dt = date.fromisoformat(args.date) if args.date else date.today()
        collect_tariffs(dt, args.cabinet)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5.4: Прогнать тесты — должны пройти**

```bash
pytest tests/audit/test_etl.py -v
```

Expected: passed.

- [ ] **Step 5.5: Коммит**

```bash
git add audit/etl/tariff_collector.py tests/audit/test_etl.py
git commit -m "refactor(etl): tariff_collector writes to SQLite via INSERT ... ON CONFLICT"
```

---

## Task 6: check_setup.py — заменить Supabase-чек на SQLite-чек

**Files:**
- Modify: `check_setup.py`
- Modify: `tests/test_check_setup.py`

- [ ] **Step 6.1: Переписать тесты для `check_sqlite`**

В `tests/test_check_setup.py` удалить `test_check_supabase_missing_credentials`. Добавить:

```python
def test_check_sqlite_db_missing(tmp_path, monkeypatch):
    from check_setup import check_sqlite
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(tmp_path / "missing.db"))
    ok, msg = check_sqlite()
    assert ok is False
    assert "not found" in msg.lower() or "missing" in msg.lower()


def test_check_sqlite_db_no_recent_tariffs(tmp_path, monkeypatch):
    import sqlite3
    db_path = tmp_path / "stale.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE wb_tariffs (dt TEXT, warehouse_name TEXT,
            delivery_coef REAL, logistics_1l REAL, logistics_extra_l REAL,
            box_storage_base REAL, storage_coef REAL, geo_name TEXT,
            created_at TEXT, PRIMARY KEY (dt, warehouse_name));
    """)
    conn.execute(
        "INSERT INTO wb_tariffs (dt, warehouse_name, created_at) VALUES (?, ?, ?)",
        ("2020-01-01", "OldWarehouse", "2020-01-01"),
    )
    conn.commit()
    conn.close()

    from check_setup import check_sqlite
    ok, msg = check_sqlite()
    assert ok is False
    assert "7 days" in msg or "stale" in msg.lower()


def test_check_sqlite_db_with_recent_tariffs(tmp_path, monkeypatch):
    import sqlite3
    from datetime import date
    db_path = tmp_path / "fresh.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE wb_tariffs (dt TEXT, warehouse_name TEXT,
            delivery_coef REAL, logistics_1l REAL, logistics_extra_l REAL,
            box_storage_base REAL, storage_coef REAL, geo_name TEXT,
            created_at TEXT, PRIMARY KEY (dt, warehouse_name));
    """)
    conn.execute(
        "INSERT INTO wb_tariffs (dt, warehouse_name, created_at) VALUES (?, ?, ?)",
        (date.today().isoformat(), "Коледино", date.today().isoformat()),
    )
    conn.commit()
    conn.close()

    from check_setup import check_sqlite
    ok, msg = check_sqlite()
    assert ok is True
    assert "OK" in msg or "tariffs" in msg.lower()
```

- [ ] **Step 6.2: Прогнать — должно упасть**

```bash
pytest tests/test_check_setup.py -v
```

Expected: ImportError / AttributeError на `check_sqlite`.

- [ ] **Step 6.3: Заменить `check_supabase` на `check_sqlite` в `check_setup.py`**

Заменить функцию:

```python
def check_supabase() -> tuple[bool, str]:
    ...
```

на:

```python
def check_sqlite() -> tuple[bool, str]:
    import sqlite3
    from datetime import date, timedelta

    db_path = Path(os.environ.get("WB_TOOLKIT_DB_PATH") or "data/wb_toolkit.db")
    if not db_path.exists():
        return False, (
            f"SQLite database not found at '{db_path}'. "
            "Run: python audit/etl/tariff_collector.py --backfill 7"
        )
    try:
        conn = sqlite3.connect(str(db_path))
        cutoff = (date.today() - timedelta(days=7)).isoformat()
        row = conn.execute(
            "SELECT COUNT(*) FROM wb_tariffs WHERE dt >= ?",
            (cutoff,),
        ).fetchone()
        conn.close()
        count = row[0] if row else 0
    except sqlite3.Error as e:
        return False, f"SQLite query failed: {e}"

    if count == 0:
        return False, (
            f"SQLite '{db_path}' has no tariffs in the last 7 days. "
            "Run: python audit/etl/tariff_collector.py --backfill 7"
        )
    return True, f"SQLite OK, {count} tariff rows in last 7 days"
```

И в списке `CHECKS` заменить:

```python
("🗄️  Supabase connection", check_supabase),
```

на:

```python
("🗄️  SQLite tariffs", check_sqlite),
```

- [ ] **Step 6.4: Прогнать тесты — должны пройти**

```bash
pytest tests/test_check_setup.py -v
```

Expected: все passed.

- [ ] **Step 6.5: Коммит**

```bash
git add check_setup.py tests/test_check_setup.py
git commit -m "refactor(check_setup): replace Supabase check with local SQLite check"
```

---

## Task 7: Удалить supabase-зависимости и legacy-файлы

**Files:**
- Delete: `shared/supabase.py`
- Delete: `audit/etl/import_coeff_table.py`
- Modify: `requirements.txt`
- Modify: `.env.example`

- [ ] **Step 7.1: Поискать остаточные импорты**

```bash
grep -rn "from shared.supabase\|import.*supabase" --include="*.py" . | grep -v __pycache__ | grep -v .venv | grep -v scripts/migrate_supabase_to_sqlite.py
```

Expected: пусто (или только сам `shared/supabase.py`).

Если что-то нашлось — открыть файл и заменить (либо вынести импорт в Task-исключение, обсудив с пользователем).

- [ ] **Step 7.2: Поискать остаточные строки "Supabase" в Excel-генераторах**

```bash
grep -rn "supabase" --include="*.py" audit/output/ | grep -v __pycache__
```

Если найдёт строку вида `if source == "supabase":` — заменить на `if source == "sqlite":` (см. Task 3.4 примечание).

- [ ] **Step 7.3: Удалить файлы**

```bash
git rm shared/supabase.py audit/etl/import_coeff_table.py
```

- [ ] **Step 7.4: Убрать `supabase>=2.4.0` из `requirements.txt`**

Открыть `requirements.txt` и удалить строку `supabase>=2.4.0`. Должно остаться:

```
httpx>=0.27.0
pandas>=2.2.0
openpyxl>=3.1.2
google-auth>=2.29.0
gspread>=6.1.0
python-dotenv>=1.0.1
PyYAML>=6.0.1
pytest>=8.1.0
pytest-mock>=3.14.0
```

- [ ] **Step 7.5: Обновить `.env.example`**

Полностью заменить содержимое:

```
# WB API tokens — name matches cabinet `name` in cabinets.yaml (uppercase)
WB_TOKEN_OOO=eyJ...
WB_TOKEN_IP=eyJ...

# Google Service Account credentials file path (optional — only for Sheets export)
GOOGLE_CREDENTIALS_PATH=credentials.json

# Local SQLite for tariff history
WB_TOOLKIT_DB_PATH=data/wb_toolkit.db
```

- [ ] **Step 7.6: Прогнать весь pytest — sanity check**

```bash
pytest -q
```

Expected: всё passed (то же количество, что и в baseline, ± новые тесты Task 1-6).

- [ ] **Step 7.7: Удалить supabase из venv (необязательно, но проверочно)**

```bash
.venv/bin/pip uninstall -y supabase
.venv/bin/pip install -r requirements.txt
pytest -q
```

Expected: всё ещё passed — это финальное доказательство, что код больше нигде не использует Supabase.

- [ ] **Step 7.8: Коммит**

```bash
git add requirements.txt .env.example
git commit -m "chore: remove Supabase dependency and legacy bootstrap files"
```

---

## Task 8: scripts/migrate_supabase_to_sqlite.py — одноразовый migration

**Files:**
- Create: `scripts/migrate_supabase_to_sqlite.py`

> **Контекст:** Этот скрипт запускается ОДИН РАЗ — на ноутбуке (где есть и Supabase-creds, и куда мы хотим положить SQLite-файл) либо потом на сервере. Он временно переинсталлирует `supabase` пакет в venv, выкачивает данные, заливает в SQLite, и затем удаляется коммитом в Task 9.

- [ ] **Step 8.1: Создать `scripts/migrate_supabase_to_sqlite.py`**

```python
#!/usr/bin/env python3
"""ONE-SHOT: migrate wb_tariffs rows from Supabase to local SQLite.

Run once when cutting over from Supabase to SQLite. Requires `supabase`
package temporarily installed AND SUPABASE_URL/SUPABASE_KEY in .env.

Usage:
    .venv/bin/pip install supabase
    python scripts/migrate_supabase_to_sqlite.py
    .venv/bin/pip uninstall -y supabase

After running, delete this script (it has no purpose post-migration).
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from shared.db import get_connection

logger = logging.getLogger(__name__)


_INSERT_SQL = """
INSERT OR REPLACE INTO wb_tariffs (
    dt, warehouse_name, delivery_coef, logistics_1l, logistics_extra_l,
    box_storage_base, storage_coef, geo_name
) VALUES (
    :dt, :warehouse_name, :delivery_coef, :logistics_1l, :logistics_extra_l,
    :box_storage_base, :storage_coef, :geo_name
)
"""


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env", file=sys.stderr)
        return 2

    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase package not installed.\n"
              "Run: .venv/bin/pip install supabase", file=sys.stderr)
        return 2

    client = create_client(url, key)
    page_size = 1000
    offset = 0
    total = 0
    conn = get_connection()

    while True:
        response = (
            client.table("wb_tariffs")
            .select("dt, warehouse_name, delivery_coef, logistics_1l, "
                    "logistics_extra_l, box_storage_base, storage_coef, geo_name")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            break
        conn.executemany(_INSERT_SQL, rows)
        conn.commit()
        total += len(rows)
        logger.info("Migrated %d rows (running total: %d)", len(rows), total)
        if len(rows) < page_size:
            break
        offset += page_size

    print(f"Done: {total} wb_tariffs rows migrated to SQLite")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8.2: Установить supabase временно и прогнать миграцию**

```bash
.venv/bin/pip install supabase
python scripts/migrate_supabase_to_sqlite.py
```

Expected output: `Done: <N> wb_tariffs rows migrated to SQLite`, где N ≥ 60. Файл `data/wb_toolkit.db` создан.

- [ ] **Step 8.3: Проверить данные в SQLite**

```bash
sqlite3 data/wb_toolkit.db "SELECT count(*), min(dt), max(dt), count(DISTINCT warehouse_name) FROM wb_tariffs;"
```

Expected: count ≥ 60, диапазон дат — последние 60 дней, разных складов ≥ 50.

- [ ] **Step 8.4: Прогнать full audit, чтобы доказать SQLite работает в продакшен-сценарии**

```bash
python audit/run_audit.py ooo 2026-03-07 2026-05-05
```

Expected: Excel-файл `Аудит логистики 2026-03-07 — 2026-05-05.xlsx` сгенерирован в текущем каталоге, переплата ≈ 4.8% / ~293k₽ (как в baseline).

- [ ] **Step 8.5: Деинсталлировать supabase из venv**

```bash
.venv/bin/pip uninstall -y supabase
pytest -q
```

Expected: pytest passed без supabase в venv.

- [ ] **Step 8.6: Коммит migration-скрипта**

```bash
git add scripts/migrate_supabase_to_sqlite.py
git commit -m "feat(migration): one-shot Supabase → SQLite copy script"
```

---

## Task 9: Удалить migration-скрипт и финальная проверка

**Files:**
- Delete: `scripts/migrate_supabase_to_sqlite.py`

- [ ] **Step 9.1: Удалить migration-скрипт**

```bash
git rm scripts/migrate_supabase_to_sqlite.py
```

> **Note:** Скрипт был выполнен в Task 8 — больше не нужен. Если понадобится повторить (например, для свежей инсталляции на новом сервере) — можно достать через `git show <sha>:scripts/migrate_supabase_to_sqlite.py`.

- [ ] **Step 9.2: Полный sanity check**

```bash
# 1. pytest
pytest -q

# 2. Никаких упоминаний Supabase в коде
grep -rE "supabase|SUPABASE_" --include="*.py" . | grep -v __pycache__ | grep -v .venv

# 3. Никаких упоминаний в requirements
grep -i supabase requirements.txt

# 4. Audit ещё работает
python audit/run_audit.py ooo 2026-03-07 2026-05-05
```

Expected:
- pytest: 145+ passed, 0 failed (точное число зависит от добавленных тестов в Tasks 1, 3, 5, 6).
- grep по `*.py`: пусто.
- grep по requirements.txt: пусто.
- audit: Excel сгенерирован, переплата ≈ 4.8%.

- [ ] **Step 9.3: check_setup проходит 6/6**

```bash
python check_setup.py
```

Expected: все 7 чеков (env, creds, creds-not-staged, cabinets, warehouse_status, WB tokens, SQLite) — ✅. Если creds.json нет — этот ❌ ожидаем; остальные 6 должны быть зелёные.

- [ ] **Step 9.4: Коммит финал**

```bash
git add -A
git commit -m "chore(migration): remove one-shot Supabase migration script after cutover"
```

- [ ] **Step 9.5: Push и PR**

```bash
git push -u origin feat/phase-a-sqlite
```

Создать PR с заголовком: `Phase А: replace Supabase with local SQLite + embedded coeff table`.

В описание PR включить:
- ссылку на спек: `docs/specs/2026-05-09-finalize-v1-design.md`
- ссылку на этот план: `docs/plans/2026-05-09-phase-a-sqlite-migration.md`
- summary diff: «убрали supabase из 4 файлов + requirements; добавили `shared/db.py` + embedded `COEFF_TABLE`; миграция данных выполнена one-shot скриптом, скрипт удалён»

---

## Acceptance criteria этого плана

- [ ] `pytest -q` → ≥ 145 passed, 0 failed (новые тесты Task 1, 3, 5, 6 = +12 как минимум)
- [ ] `grep -rE "supabase|SUPABASE_" --include="*.py" .` → пусто
- [ ] `grep -i supabase requirements.txt` → пусто
- [ ] `data/wb_toolkit.db` существует, ≥ 60 строк в `wb_tariffs`
- [ ] `python audit/run_audit.py ooo 2026-03-07 2026-05-05` генерирует Excel с переплатой ≈ 4.8%
- [ ] `python check_setup.py` показывает SQLite-чек ✅ (Supabase-чек удалён)
- [ ] PR `feat/phase-a-sqlite` готов к мерджу

После мерджа этого плана — следующий план: **Фаза Б — Excel-fallback writer + унификация GOOGLE_CREDENTIALS_PATH**.
