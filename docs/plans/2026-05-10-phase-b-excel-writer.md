# Phase Б: Excel-fallback Writer + Credentials Unification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** заменить жёсткую зависимость локализации (3 фазы) от Google Sheets на полиморфный Writer, который по правилу из §1.2 спека сам решает писать в Sheets или в локальный Excel. Унифицировать `GOOGLE_CREDENTIALS_PATH` (вместо текущего `_JSON`).

**Architecture:** Внедряем Protocol `Writer` с двумя реализациями — `SheetsWriter` (тонкая обёртка над gspread, переезжает текущая логика) и `ExcelWriter` (новая, openpyxl, несколько листов в одном `.xlsx`). Все три writer-функции (`write_analysis`, `write_roadmap`, `write_permutations`) принимают `Writer` вместо `gspread.Spreadsheet`. Раннеры выбирают конкретный writer по правилу: `sheet_id` валиден И `credentials.json` существует И `--no-sheets` не указан → SheetsWriter; иначе ExcelWriter.

**Tech Stack:** Python 3.11+, `openpyxl` (уже в requirements), `gspread` (уже в requirements). Никаких новых зависимостей.

**Spec:** [docs/specs/2026-05-09-finalize-v1-design.md](../specs/2026-05-09-finalize-v1-design.md) §1.2, §5 Фаза Б.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `localization/output/__init__.py` | Create | пустой пакетный маркер |
| `localization/output/writer.py` | Create | `Writer` Protocol + `SheetsWriter` + `ExcelWriter` + factory `make_writer()` |
| `localization/output/analysis_writer.py` | Create | refactor `localization/sheets/analysis_writer.py` под `Writer` |
| `localization/output/roadmap_writer.py` | Create | refactor `localization/sheets/roadmap_writer.py` |
| `localization/output/permutations_writer.py` | Create | refactor `localization/sheets/permutations_writer.py` |
| `localization/run_analysis.py` | Modify | добавить `--no-sheets`, использовать `make_writer()` |
| `localization/run_roadmap.py` | Modify | то же |
| `localization/run_permutations.py` | Modify | то же |
| `shared/sheets_client.py` | Modify | `GOOGLE_CREDENTIALS_JSON` → `GOOGLE_CREDENTIALS_PATH` |
| `cabinets.yaml` | Modify | `sheet_id: ""` для обоих кабинетов (placeholder убрать) |
| `.gitignore` | Modify | `localization/data/output/` |
| `tests/localization/output/__init__.py` | Create | empty |
| `tests/localization/output/test_writer.py` | Create | unit-тесты для `ExcelWriter` + `make_writer()` |
| `localization/sheets/` | Delete | старые модули после миграции |

**Не трогаем:**
- `audit/output/` — отдельный мир (Excel-генератор аудита, не имеет отношения к локализации)
- Калькуляторы `localization/calculators/` — на них не влияем

---

## Branch Setup

- [ ] **Step 0.1: Создать ветку из main**

```bash
cd ~/Projects/wb-logistics-toolkit
git checkout main
git pull --ff-only
git status                                    # clean
git checkout -b feat/phase-b-excel-writer
```

- [ ] **Step 0.2: Baseline pytest**

```bash
.venv/bin/pytest -q
```

Expected: 157 passed, 0 failed.

---

## Task 1: localization/output/writer.py — Protocol + Implementations

**Files:**
- Create: `localization/output/__init__.py` (empty)
- Create: `localization/output/writer.py`
- Create: `tests/localization/output/__init__.py` (empty)
- Create: `tests/localization/output/test_writer.py`

- [ ] **Step 1.1: Failing tests for ExcelWriter и make_writer**

Создать `tests/localization/output/test_writer.py`:

```python
# tests/localization/output/test_writer.py
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from openpyxl import load_workbook

from localization.output.writer import ExcelWriter, SheetsWriter, make_writer


def test_excel_writer_creates_file_with_multiple_sheets(tmp_path):
    out = tmp_path / "test.xlsx"
    w = ExcelWriter(str(out))
    w.write_sheet("Анализ", [["Артикул", "Цена"], ["ABC", 100], ["DEF", 200]])
    w.write_sheet("Сводка", [["Метрика", "Значение"], ["ИЛ %", 75.5]])
    path = w.finalize()

    assert path == str(out)
    assert out.exists()

    wb = load_workbook(out)
    assert set(wb.sheetnames) == {"Анализ", "Сводка"}
    assert wb["Анализ"].cell(1, 1).value == "Артикул"
    assert wb["Анализ"].cell(2, 2).value == 100
    assert wb["Сводка"].cell(2, 2).value == 75.5


def test_excel_writer_overwrites_existing_file(tmp_path):
    out = tmp_path / "exists.xlsx"
    out.write_bytes(b"junk")
    w = ExcelWriter(str(out))
    w.write_sheet("OnlySheet", [["A"], ["B"]])
    w.finalize()
    wb = load_workbook(out)
    assert wb.sheetnames == ["OnlySheet"]


def test_excel_writer_handles_empty_data(tmp_path):
    out = tmp_path / "empty.xlsx"
    w = ExcelWriter(str(out))
    w.write_sheet("Empty", [])
    w.finalize()
    wb = load_workbook(out)
    assert wb["Empty"].max_row == 1   # openpyxl creates 1 phantom row


def test_excel_writer_creates_parent_dir(tmp_path):
    out = tmp_path / "nested" / "deep" / "out.xlsx"
    w = ExcelWriter(str(out))
    w.write_sheet("S", [["x"]])
    w.finalize()
    assert out.exists()


def test_make_writer_picks_excel_when_no_sheet_id(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", "")
    w = make_writer(
        cabinet_name="ooo",
        sheet_id="",
        excel_path=str(tmp_path / "out.xlsx"),
        force_excel=False,
    )
    assert isinstance(w, ExcelWriter)


def test_make_writer_picks_excel_when_placeholder_sheet_id(tmp_path):
    w = make_writer(
        cabinet_name="ooo",
        sheet_id="YOUR_SHEET_ID_HERE",
        excel_path=str(tmp_path / "out.xlsx"),
        force_excel=False,
    )
    assert isinstance(w, ExcelWriter)


def test_make_writer_picks_excel_when_creds_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(tmp_path / "missing.json"))
    w = make_writer(
        cabinet_name="ooo",
        sheet_id="1AbCxyz",
        excel_path=str(tmp_path / "out.xlsx"),
        force_excel=False,
    )
    assert isinstance(w, ExcelWriter)


def test_make_writer_force_excel_overrides_valid_config(tmp_path, monkeypatch):
    creds = tmp_path / "creds.json"
    creds.write_text("{}")
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(creds))
    w = make_writer(
        cabinet_name="ooo",
        sheet_id="1AbCxyz",
        excel_path=str(tmp_path / "out.xlsx"),
        force_excel=True,
    )
    assert isinstance(w, ExcelWriter)


def test_make_writer_picks_sheets_when_all_conditions_met(tmp_path, monkeypatch):
    creds = tmp_path / "creds.json"
    creds.write_text("{}")
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(creds))
    fake_spreadsheet = object()
    with patch(
        "localization.output.writer._open_spreadsheet",
        return_value=fake_spreadsheet,
    ) as mock_open:
        w = make_writer(
            cabinet_name="ooo",
            sheet_id="1AbCxyz",
            excel_path=str(tmp_path / "out.xlsx"),
            force_excel=False,
        )
    assert isinstance(w, SheetsWriter)
    mock_open.assert_called_once_with("1AbCxyz")
```

- [ ] **Step 1.2: Run tests — should fail**

```bash
.venv/bin/pytest tests/localization/output/test_writer.py -v
```

Expected: ImportError на `localization.output.writer`.

- [ ] **Step 1.3: Создать `localization/output/__init__.py`**

```python
# localization/output/__init__.py
```

(пустой файл-маркер пакета)

- [ ] **Step 1.4: Создать `tests/localization/output/__init__.py`**

```python
# tests/localization/output/__init__.py
```

- [ ] **Step 1.5: Создать `localization/output/writer.py`**

```python
"""Output writers for localization phases.

Two implementations behind a single `Writer` Protocol:
- `SheetsWriter` writes to Google Sheets (via gspread).
- `ExcelWriter` writes to a local `.xlsx` file (via openpyxl).

`make_writer()` is the factory: it picks one based on cabinet config + env.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol

from openpyxl import Workbook


class Writer(Protocol):
    """Sink for tabular sheet data. Implementations decide where rows go."""

    def write_sheet(self, name: str, rows: list[list[Any]]) -> None:
        """Write `rows` to a sheet identified by `name` (idempotent / replace)."""
        ...

    def finalize(self) -> str | None:
        """Flush pending writes. Returns local path for Excel, None for Sheets."""
        ...


class ExcelWriter:
    """openpyxl-backed writer. Buffers sheets in memory, saves on `finalize()`."""

    def __init__(self, output_path: str) -> None:
        self._output_path = output_path
        self._wb = Workbook()
        # Workbook starts with a default "Sheet" — we'll remove it lazily once
        # the first real sheet arrives. If finalize() runs without any writes
        # at all, leave the default in place so the file is at least valid.
        self._default_removed = False

    def write_sheet(self, name: str, rows: list[list[Any]]) -> None:
        if not self._default_removed:
            default = self._wb.active
            if default is not None and default.title == "Sheet":
                self._wb.remove(default)
            self._default_removed = True
        ws = self._wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)

    def finalize(self) -> str:
        Path(self._output_path).parent.mkdir(parents=True, exist_ok=True)
        self._wb.save(self._output_path)
        return self._output_path


class SheetsWriter:
    """gspread-backed writer. Each `write_sheet` call upserts a worksheet."""

    def __init__(self, spreadsheet: Any) -> None:
        # `Any` to avoid an unconditional gspread import at module load time;
        # the runner provides a real `gspread.Spreadsheet`.
        self._spreadsheet = spreadsheet

    def write_sheet(self, name: str, rows: list[list[Any]]) -> None:
        from shared.sheets_client import clear_and_write, get_or_create_worksheet
        ws = get_or_create_worksheet(self._spreadsheet, name)
        clear_and_write(ws, rows)

    def finalize(self) -> None:
        return None


def _open_spreadsheet(sheet_id: str) -> Any:
    """Open a gspread spreadsheet by id. Indirected so tests can patch it."""
    from shared.sheets_client import get_client
    gc = get_client()
    return gc.open_by_key(sheet_id)


def make_writer(
    *,
    cabinet_name: str,
    sheet_id: str | None,
    excel_path: str,
    force_excel: bool,
) -> Writer:
    """Pick a writer per spec §1.2.

    Excel-fallback is the default: SheetsWriter is only chosen when ALL hold —
    `sheet_id` is set and not the YAML placeholder, `--no-sheets` was not
    passed, and `GOOGLE_CREDENTIALS_PATH` points to an existing file.
    """
    if force_excel:
        return ExcelWriter(excel_path)

    sheet_id_clean = (sheet_id or "").strip()
    if not sheet_id_clean or sheet_id_clean == "YOUR_SHEET_ID_HERE":
        return ExcelWriter(excel_path)

    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "").strip()
    if not creds_path or not Path(creds_path).exists():
        return ExcelWriter(excel_path)

    spreadsheet = _open_spreadsheet(sheet_id_clean)
    return SheetsWriter(spreadsheet)
```

- [ ] **Step 1.6: Run tests — should pass**

```bash
.venv/bin/pytest tests/localization/output/test_writer.py -v
```

Expected: 9 passed.

- [ ] **Step 1.7: Commit**

```bash
git add localization/output/__init__.py localization/output/writer.py \
        tests/localization/output/__init__.py tests/localization/output/test_writer.py
git commit -m "feat(localization): Writer Protocol with Excel + Sheets implementations"
```

---

## Task 2: Refactor analysis writer to use Writer

**Files:**
- Create: `localization/output/analysis_writer.py`

- [ ] **Step 2.1: Создать `localization/output/analysis_writer.py`**

Скопировать содержимое `localization/sheets/analysis_writer.py`, заменить:

- сигнатуру `write_analysis(spreadsheet: gspread.Spreadsheet, ...)` → `write_analysis(writer: Writer, ...)`
- `_write_articles(spreadsheet, ...)` → `_write_articles(writer, ...)` и так для остальных трёх helpers
- везде в helpers: `ws = get_or_create_worksheet(spreadsheet, "...")` + `clear_and_write(ws, rows)` → `writer.write_sheet("...", rows)`
- импорт `from shared.sheets_client import clear_and_write, get_or_create_worksheet, to_number` → `from shared.sheets_client import to_number` (только `to_number` остаётся)
- импорт `import gspread` — убрать
- добавить `from localization.output.writer import Writer`

Результат должен скомпилироваться и иметь тот же набор имён (write_analysis), но принимать Writer.

```python
"""Write Phase 1 (ИЛ/ИРП) analysis results via a Writer."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.sheets_client import to_number

from localization.output.writer import Writer


def write_analysis(
    writer: Writer,
    il_irp: dict[str, Any],
    scenarios: dict[str, Any],
) -> None:
    """Write ИЛ/ИРП analysis and scenario tables via the writer."""
    _write_articles(writer, il_irp.get("articles", []))
    _write_scenarios(writer, scenarios)
    _write_top_problems(writer, il_irp.get("top_problems", []))
    _write_dashboard(writer, il_irp.get("summary", {}), scenarios)


def _write_articles(writer: Writer, articles: list[dict[str, Any]]) -> None:
    header = [
        "Артикул", "Локальных", "Нелокальных", "Всего", "Локал. %",
        "КТР", "КРП %", "Статус", "Цена", "ИРП/заказ ₽", "ИРП/мес ₽",
        "Вклад в ИЛ", "Слабый регион",
    ]
    rows = [header]
    for a in articles:
        rows.append([
            a.get("article", ""),
            to_number(a.get("wb_local", 0)),
            to_number(a.get("wb_nonlocal", 0)),
            to_number(a.get("wb_total", 0)),
            to_number(a.get("loc_pct", 0)),
            to_number(a.get("ktr", 0)),
            to_number(a.get("krp_pct", 0)),
            a.get("status", ""),
            to_number(a.get("price", 0)),
            to_number(a.get("irp_per_order", 0)),
            to_number(a.get("irp_per_month", 0)),
            to_number(a.get("contribution", 0)),
            a.get("weakest_region", ""),
        ])
    writer.write_sheet("ИЛ-ИРП Анализ", rows)


def _write_scenarios(writer: Writer, scenarios: dict[str, Any]) -> None:
    header = [
        "Уровень лок. %", "Логистика ₽/мес", "ИРП ₽/мес", "Итого ₽/мес",
        "КТР", "КРП %", "Δ к текущему ₽", "Δ к худшему ₽",
    ]
    rows = [header]
    current = scenarios.get("current_scenario", {})
    rows.append([
        f"{current.get('level_pct', 0):.1f} (сейчас)",
        to_number(current.get("logistics_monthly", 0)),
        to_number(current.get("irp_monthly", 0)),
        to_number(current.get("total_monthly", 0)),
        "", "", "", "",
    ])
    for sc in scenarios.get("scenarios", []):
        rows.append([
            to_number(sc.get("level_pct", 0)),
            to_number(sc.get("logistics_monthly", 0)),
            to_number(sc.get("irp_monthly", 0)),
            to_number(sc.get("total_monthly", 0)),
            to_number(sc.get("ktr", 0)),
            to_number(sc.get("krp_pct", 0)),
            to_number(sc.get("delta_vs_current", 0)),
            to_number(sc.get("delta_vs_worst", 0)),
        ])
    writer.write_sheet("Сценарии", rows)


def _write_top_problems(writer: Writer, top_problems: list[dict[str, Any]]) -> None:
    header = [
        "#", "Артикул", "Заказов", "Лок. %", "КТР", "КРП %",
        "Вклад в ИЛ", "Слабый регион", "Рекомендация",
    ]
    rows = [header]
    for p in top_problems:
        rows.append([
            to_number(p.get("rank", 0)),
            p.get("article", ""),
            to_number(p.get("orders", 0)),
            to_number(p.get("loc_pct", 0)),
            to_number(p.get("ktr", 0)),
            to_number(p.get("krp_pct", 0)),
            to_number(p.get("contribution", 0)),
            p.get("weakest_region", ""),
            p.get("recommendation", ""),
        ])
    writer.write_sheet("Топ проблем", rows)


def _write_dashboard(
    writer: Writer, summary: dict[str, Any], scenarios: dict[str, Any]
) -> None:
    eco = scenarios.get("relocation_economics", {})
    rows = [
        ["Обновлено", datetime.now().strftime("%d.%m.%Y %H:%M")],
        [""],
        ["=== ИЛ/ИРП ==="],
        ["ИЛ (КТР weighted)", to_number(summary.get("overall_il", 0))],
        ["Локализация %", to_number(summary.get("loc_pct", 0))],
        ["RF заказов", to_number(summary.get("total_rf_orders", 0))],
        ["Артикулов", to_number(summary.get("total_articles", 0))],
        ["ИРП-зона артикулов", to_number(summary.get("irp_zone_articles", 0))],
        ["ИРП убыток ₽/мес", to_number(summary.get("irp_monthly_cost_rub", 0))],
        [""],
        ["=== ЭКОНОМИКА ПЕРЕСТАНОВОК (→80%) ==="],
        ["Оборот ₽/мес", to_number(eco.get("turnover_monthly", 0))],
        ["Комиссия перестановок ₽/мес", to_number(eco.get("commission_monthly", 0))],
        ["Макс. экономия ₽/мес", to_number(eco.get("max_savings_monthly", 0))],
        ["Чистая выгода ₽/мес", to_number(eco.get("net_benefit_monthly", 0))],
    ]
    writer.write_sheet("Дашборд ИЛ", rows)
```

- [ ] **Step 2.2: Sanity-prove with ExcelWriter end-to-end (smoke)**

```bash
.venv/bin/python -c "
from localization.output.writer import ExcelWriter
from localization.output.analysis_writer import write_analysis
w = ExcelWriter('/tmp/_phase_b_smoke.xlsx')
write_analysis(w, {'articles': [], 'top_problems': [], 'summary': {}}, {'scenarios': []})
print(w.finalize())
"
```

Expected: prints `/tmp/_phase_b_smoke.xlsx` and the file exists with 4 sheets.

- [ ] **Step 2.3: Commit**

```bash
git add localization/output/analysis_writer.py
git commit -m "refactor(localization): port analysis writer to Writer protocol"
```

---

## Task 3: Refactor roadmap writer to use Writer

**Files:**
- Create: `localization/output/roadmap_writer.py`

- [ ] **Step 3.1: Создать `localization/output/roadmap_writer.py`**

```python
"""Write Phase 2 (13-week roadmap) via a Writer."""
from __future__ import annotations

from typing import Any

from shared.sheets_client import to_number

from localization.output.writer import Writer


def write_roadmap(writer: Writer, roadmap_result: dict[str, Any]) -> None:
    """Write simulate_roadmap() output to sheet "Роадмап 13 нед."."""
    params = roadmap_result.get("params", {})
    milestones = roadmap_result.get("milestones", {})
    roadmap = roadmap_result.get("roadmap", [])

    meta_rows = [
        ["Параметры"],
        ["Цель локализации %", to_number(params.get("target_localization", 85))],
        ["Реалистичная доля слотов", to_number(params.get("realistic_limit_pct", 0.3))],
        ["Всего перемещений шт", to_number(params.get("total_plan_qty", 0))],
        ["Артикулов с движением", to_number(params.get("articles_with_movements", 0))],
        [""],
        ["Вехи"],
        ["Неделя достижения 60%", to_number(milestones.get("week_60pct") or "—")],
        ["Неделя достижения 80%", to_number(milestones.get("week_80pct") or "—")],
        [""],
    ]

    header = [
        "Неделя", "Дата", "Перемещено шт (накоп.)", "Выполнено %",
        "Прогноз лок. %", "КТР weighted", "Логистика ₽/мес",
        "ИРП ₽/мес", "Итого ₽/мес", "Экономия ₽/мес",
    ]
    data_rows = [header]
    for week in roadmap:
        data_rows.append([
            to_number(week.get("week")),
            week.get("date", ""),
            to_number(week.get("moved_units_cumulative", 0)),
            to_number(week.get("plan_pct", 0)),
            to_number(week.get("il_forecast", 0)),
            to_number(week.get("ktr_weighted", 0)),
            to_number(week.get("logistics_monthly", 0)),
            to_number(week.get("irp_monthly", 0)),
            to_number(week.get("total_monthly", 0)),
            to_number(week.get("savings_vs_current", 0)),
        ])

    writer.write_sheet("Роадмап 13 нед.", meta_rows + data_rows)
```

- [ ] **Step 3.2: Smoke**

```bash
.venv/bin/python -c "
from localization.output.writer import ExcelWriter
from localization.output.roadmap_writer import write_roadmap
w = ExcelWriter('/tmp/_phase_b_smoke_roadmap.xlsx')
write_roadmap(w, {'params': {}, 'milestones': {}, 'roadmap': []})
print(w.finalize())
"
```

Expected: file exists with 1 sheet ("Роадмап 13 нед.").

- [ ] **Step 3.3: Commit**

```bash
git add localization/output/roadmap_writer.py
git commit -m "refactor(localization): port roadmap writer to Writer protocol"
```

---

## Task 4: Refactor permutations writer to use Writer

**Files:**
- Create: `localization/output/permutations_writer.py`

- [ ] **Step 4.1: Создать `localization/output/permutations_writer.py`**

```python
"""Write Phase 3 (permutation recommendations) via a Writer."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.sheets_client import to_number

from localization.output.writer import Writer


def write_permutations(writer: Writer, permutation_result: dict[str, Any]) -> None:
    """Write generate_movements() output to four sheets."""
    _write_movements(writer, permutation_result.get("movements", []))
    _write_supplies(writer, permutation_result.get("supplies", []))
    _write_region_summary(writer, permutation_result.get("region_summary", []))
    _write_update_timestamp(writer)


def _write_movements(writer: Writer, movements: list[dict[str, Any]]) -> None:
    header = [
        "Артикул", "Откуда ФО", "Откуда склад",
        "Куда ФО", "Куда склад", "Кол-во шт",
    ]
    rows = [header]
    for m in movements:
        rows.append([
            m.get("article", ""),
            m.get("from_fd", ""),
            m.get("from_warehouse", ""),
            m.get("to_fd", ""),
            m.get("to_warehouse", ""),
            to_number(m.get("qty", 0)),
        ])
    writer.write_sheet("Перемещения", rows)


def _write_supplies(writer: Writer, supplies: list[dict[str, Any]]) -> None:
    header = ["Артикул", "Куда ФО", "Куда склад", "Кол-во шт"]
    rows = [header]
    for s in supplies:
        rows.append([
            s.get("article", ""),
            s.get("to_fd", ""),
            s.get("to_warehouse", ""),
            to_number(s.get("qty", 0)),
        ])
    writer.write_sheet("Допоставки", rows)


def _write_region_summary(
    writer: Writer, region_summary: list[dict[str, Any]]
) -> None:
    header = ["ФО", "Остатки шт", "Заказов шт", "Лок. %"]
    rows = [header]
    for r in region_summary:
        rows.append([
            r.get("fd", ""),
            to_number(r.get("stock_total", 0)),
            to_number(r.get("orders_total", 0)),
            to_number(r.get("loc_pct", 0)),
        ])
    writer.write_sheet("Сводка регионов", rows)


def _write_update_timestamp(writer: Writer) -> None:
    writer.write_sheet("Обновление", [
        ["Обновлено", datetime.now().strftime("%d.%m.%Y %H:%M")],
        ["Источник", "WB API (warehouse/remains + supplier/orders + reportDetailByPeriod)"],
    ])
```

- [ ] **Step 4.2: Smoke**

```bash
.venv/bin/python -c "
from localization.output.writer import ExcelWriter
from localization.output.permutations_writer import write_permutations
w = ExcelWriter('/tmp/_phase_b_smoke_perm.xlsx')
write_permutations(w, {'movements': [], 'supplies': [], 'region_summary': []})
print(w.finalize())
"
```

Expected: file exists with 4 sheets.

- [ ] **Step 4.3: Commit**

```bash
git add localization/output/permutations_writer.py
git commit -m "refactor(localization): port permutations writer to Writer protocol"
```

---

## Task 5: Integrate writer into run_analysis.py

**Files:**
- Modify: `localization/run_analysis.py`

- [ ] **Step 5.1: Заменить блок Sheets-export на writer-pattern**

В `localization/run_analysis.py` заменить hop в самом конце `main()`:

OLD:
```python
    try:
        import os
        if not os.environ.get("GOOGLE_CREDENTIALS_JSON"):
            print("  Sheets: GOOGLE_CREDENTIALS_JSON not set, skipping.")
            return
        from shared.sheets_client import get_client
        from localization.sheets.analysis_writer import write_analysis
        gc = get_client()
        spreadsheet = gc.open_by_key(cabinet.sheet_id)
        write_analysis(spreadsheet, il_irp, scenarios)
        print(f"  Sheets updated: {cabinet.sheet_id}")
    except Exception as exc:
        print(f"  Sheets export failed (non-fatal): {exc}")
```

NEW:
```python
    from localization.output.writer import ExcelWriter, SheetsWriter, make_writer
    from localization.output.analysis_writer import write_analysis

    excel_path = f"localization/data/output/Локализация Анализ {args.cabinet}.xlsx"
    try:
        writer = make_writer(
            cabinet_name=args.cabinet,
            sheet_id=cabinet.sheet_id,
            excel_path=excel_path,
            force_excel=args.no_sheets,
        )
        write_analysis(writer, il_irp, scenarios)
        out = writer.finalize()
        if isinstance(writer, SheetsWriter):
            print(f"  Sheets updated: {cabinet.sheet_id}")
        else:
            print(f"  Excel saved: {out}")
    except Exception as exc:
        print(f"  Output failed (non-fatal): {exc}")
```

- [ ] **Step 5.2: Добавить `--no-sheets` в argparse**

В `_parse_args()` (или в `main()` argparse) добавить:

```python
parser.add_argument(
    "--no-sheets",
    action="store_true",
    help="Force Excel output even if Sheets is configured",
)
```

- [ ] **Step 5.3: Sanity без живого WB API (через unit-mock не делаем, но синтаксис должен работать)**

```bash
.venv/bin/python -c "import localization.run_analysis"
.venv/bin/python localization/run_analysis.py --help 2>&1 | grep -E "no-sheets|cabinet"
```

Expected: `--help` показывает `--no-sheets` флаг и `cabinet` arg.

- [ ] **Step 5.4: Прогнать pytest**

```bash
.venv/bin/pytest -q
```

Expected: 166+ passed (157 baseline + 9 writer-tests). 0 failed.

- [ ] **Step 5.5: Commit**

```bash
git add localization/run_analysis.py
git commit -m "feat(localization): wire analysis runner to Writer + --no-sheets"
```

---

## Task 6: Integrate writer into run_roadmap.py and run_permutations.py

**Files:**
- Modify: `localization/run_roadmap.py`
- Modify: `localization/run_permutations.py`

- [ ] **Step 6.1: `run_roadmap.py` — заменить Sheets-блок аналогично Step 5.1**

OLD блок (try/except sheets) → NEW (writer-pattern):

```python
    from localization.output.writer import ExcelWriter, SheetsWriter, make_writer
    from localization.output.roadmap_writer import write_roadmap

    excel_path = f"localization/data/output/Локализация Roadmap {args.cabinet}.xlsx"
    try:
        writer = make_writer(
            cabinet_name=args.cabinet,
            sheet_id=cabinet.sheet_id,
            excel_path=excel_path,
            force_excel=args.no_sheets,
        )
        write_roadmap(writer, roadmap_result)
        out = writer.finalize()
        if isinstance(writer, SheetsWriter):
            print(f"  Sheets updated: {cabinet.sheet_id}")
        else:
            print(f"  Excel saved: {out}")
    except Exception as exc:
        print(f"  Output failed (non-fatal): {exc}")
```

Добавить `--no-sheets` флаг в `argparse`.

- [ ] **Step 6.2: `run_permutations.py` — то же**

```python
    from localization.output.writer import ExcelWriter, SheetsWriter, make_writer
    from localization.output.permutations_writer import write_permutations

    excel_path = f"localization/data/output/Локализация Перестановки {args.cabinet}.xlsx"
    try:
        writer = make_writer(
            cabinet_name=args.cabinet,
            sheet_id=cabinet.sheet_id,
            excel_path=excel_path,
            force_excel=args.no_sheets,
        )
        write_permutations(writer, result)
        out = writer.finalize()
        if isinstance(writer, SheetsWriter):
            print(f"  Sheets updated: {cabinet.sheet_id}")
        else:
            print(f"  Excel saved: {out}")
    except Exception as exc:
        print(f"  Output failed (non-fatal): {exc}")
```

Добавить `--no-sheets` флаг.

- [ ] **Step 6.3: Sanity**

```bash
.venv/bin/python -c "import localization.run_roadmap, localization.run_permutations"
.venv/bin/python localization/run_roadmap.py --help 2>&1 | grep -E "no-sheets"
.venv/bin/python localization/run_permutations.py --help 2>&1 | grep -E "no-sheets"
```

Expected: оба helps показывают `--no-sheets`.

- [ ] **Step 6.4: Pytest**

```bash
.venv/bin/pytest -q
```

Expected: 166+ passed.

- [ ] **Step 6.5: Commit**

```bash
git add localization/run_roadmap.py localization/run_permutations.py
git commit -m "feat(localization): wire roadmap+permutations runners to Writer + --no-sheets"
```

---

## Task 7: Unify GOOGLE_CREDENTIALS_PATH

**Files:**
- Modify: `shared/sheets_client.py`

- [ ] **Step 7.1: Заменить `GOOGLE_CREDENTIALS_JSON` → `GOOGLE_CREDENTIALS_PATH` в `shared/sheets_client.py`**

OLD `get_client()`:
```python
def get_client(credentials_json: str | None = None) -> gspread.Client:
    """Build authenticated gspread Client.

    Args:
        credentials_json: Path to service account JSON, or raw JSON string.
            Falls back to GOOGLE_CREDENTIALS_JSON env var if None.
    """
    raw = credentials_json or os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    if not raw:
        raise ValueError(
            "No Google credentials. Set GOOGLE_CREDENTIALS_JSON env var "
            "or pass credentials_json=."
        )
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        with open(raw, encoding="utf-8") as f:
            info = json.load(f)
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    return gspread.authorize(creds)
```

NEW (только path-форма, raw JSON убираем — `.env.example` уже на `_PATH`):
```python
def get_client(credentials_path: str | None = None) -> gspread.Client:
    """Build authenticated gspread Client.

    Args:
        credentials_path: Path to service account JSON file. Falls back to
            GOOGLE_CREDENTIALS_PATH env var if None.
    """
    path = credentials_path or os.environ.get("GOOGLE_CREDENTIALS_PATH", "")
    if not path:
        raise ValueError(
            "No Google credentials. Set GOOGLE_CREDENTIALS_PATH in .env "
            "or pass credentials_path=."
        )
    with open(path, encoding="utf-8") as f:
        info = json.load(f)
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    return gspread.authorize(creds)
```

`import json` остаётся (нужен для `json.load(f)`).

- [ ] **Step 7.2: Sanity grep**

```bash
grep -rn "GOOGLE_CREDENTIALS_JSON" --include="*.py" . | grep -v __pycache__ | grep -v ".venv"
```

Expected: empty. (`localization/run_*.py` already use `make_writer`, not direct env-var lookup.)

- [ ] **Step 7.3: Pytest**

```bash
.venv/bin/pytest -q
```

Expected: 166+ passed.

- [ ] **Step 7.4: Commit**

```bash
git add shared/sheets_client.py
git commit -m "refactor(sheets): unify on GOOGLE_CREDENTIALS_PATH (drop _JSON variant)"
```

---

## Task 8: cabinets.yaml + .gitignore + folder

**Files:**
- Modify: `cabinets.yaml`
- Modify: `.gitignore`
- Create: `localization/data/output/.gitkeep`

- [ ] **Step 8.1: `cabinets.yaml` — placeholder → ""**

OLD:
```yaml
cabinets:
  - name: ooo
    sheet_id: "YOUR_SHEET_ID_HERE"
  - name: ip
    sheet_id: "YOUR_SHEET_ID_HERE"
```

NEW:
```yaml
cabinets:
  - name: ooo
    sheet_id: ""
  - name: ip
    sheet_id: ""
```

(Header comments сохранить.)

- [ ] **Step 8.2: `.gitignore` — добавить путь к Excel-выводу**

В `.gitignore` после строки `localization/data/cache/` добавить:

```
localization/data/output/
```

> **Note:** Каталог `localization/data/output/` НЕ коммитим — он создаётся на лету через `Path(self._output_path).parent.mkdir(parents=True, exist_ok=True)` в `ExcelWriter.finalize()` (Task 1). `.gitkeep` не нужен.

- [ ] **Step 8.3: Pytest + check_setup**

```bash
.venv/bin/pytest -q
.venv/bin/python check_setup.py
```

Expected: 166+ passed; check_setup all green.

- [ ] **Step 8.4: Commit**

```bash
git add cabinets.yaml .gitignore
git commit -m "chore: cabinets.yaml empty sheet_id + gitignore localization output"
```

---

## Task 9: Delete localization/sheets/ + final sanity + PR

**Files:**
- Delete: `localization/sheets/` (всё содержимое)

- [ ] **Step 9.1: Sanity-grep — убедиться, что никто не импортирует старые модули**

```bash
grep -rn "localization.sheets\|from localization.sheets" --include="*.py" . | grep -v __pycache__ | grep -v ".venv"
```

Expected: empty.

Если найдёт — фиксить там, прежде чем удалять.

- [ ] **Step 9.2: Удалить старый каталог**

```bash
git rm -r localization/sheets/
```

- [ ] **Step 9.3: Финальный sanity**

```bash
.venv/bin/pytest -q
grep -rn "GOOGLE_CREDENTIALS_JSON\|localization.sheets" --include="*.py" . | grep -v __pycache__ | grep -v ".venv"
.venv/bin/python check_setup.py
.venv/bin/python localization/run_analysis.py --help
.venv/bin/python localization/run_roadmap.py --help
.venv/bin/python localization/run_permutations.py --help
```

Expected:
- pytest: 166+ passed, 0 failed
- grep: empty
- check_setup: all green
- все три `--help` показывают `--no-sheets`

- [ ] **Step 9.4: Smoke с ExcelWriter — мини-fixture без WB API**

```bash
.venv/bin/python -c "
from localization.output.writer import ExcelWriter
from localization.output.analysis_writer import write_analysis
from localization.output.roadmap_writer import write_roadmap
from localization.output.permutations_writer import write_permutations

w1 = ExcelWriter('/tmp/_phb_smoke_1.xlsx')
write_analysis(w1, {'articles': [{'article': 'X', 'loc_pct': 50}], 'top_problems': [], 'summary': {'overall_il': 0.7}}, {'scenarios': [], 'current_scenario': {}, 'relocation_economics': {}})
print('analysis:', w1.finalize())

w2 = ExcelWriter('/tmp/_phb_smoke_2.xlsx')
write_roadmap(w2, {'params': {}, 'milestones': {}, 'roadmap': [{'week': 1, 'date': '2026-05-12'}]})
print('roadmap:', w2.finalize())

w3 = ExcelWriter('/tmp/_phb_smoke_3.xlsx')
write_permutations(w3, {'movements': [{'article': 'X', 'from_fd': 'A', 'to_fd': 'B', 'qty': 10}], 'supplies': [], 'region_summary': []})
print('perm:', w3.finalize())
"
```

Expected: 3 файла созданы, все open в openpyxl без ошибок.

- [ ] **Step 9.5: Commit финальной чистки**

```bash
git add -A
git commit -m "chore: drop legacy localization/sheets/ — replaced by output/"
```

- [ ] **Step 9.6: Push + PR**

```bash
git push -u origin feat/phase-b-excel-writer
gh pr create --title "Phase Б: Excel-fallback writer + GOOGLE_CREDENTIALS_PATH unification" --body "$(cat <<'EOF'
## Summary
- Adds `localization/output/writer.py` — `Writer` Protocol + `ExcelWriter` (openpyxl) + `SheetsWriter` (gspread).
- All three localization phases (`analysis`, `roadmap`, `permutations`) now use the Writer abstraction.
- `make_writer()` picks Excel as default; Sheets only when `sheet_id` is set, `credentials.json` exists, AND `--no-sheets` is not passed.
- Unifies `GOOGLE_CREDENTIALS_JSON` → `GOOGLE_CREDENTIALS_PATH` (env var name + `get_client()` parameter).
- `cabinets.yaml` resets `sheet_id` to `""` for both cabinets (placeholder removed).
- Excel output goes to `localization/data/output/` (gitignored).
- Removes `localization/sheets/` entirely.

## Plan / Spec
- Spec: \`docs/specs/2026-05-09-finalize-v1-design.md\` §1.2, §5 Фаза Б
- Plan: \`docs/plans/2026-05-10-phase-b-excel-writer.md\`

## Acceptance
- [x] pytest: ≥166 passed (baseline 157 + 9 writer tests), 0 failed
- [x] No \`GOOGLE_CREDENTIALS_JSON\` in code
- [x] No \`localization.sheets\` references
- [x] All three runners support \`--no-sheets\`
- [x] Smoke: \`ExcelWriter\` produces valid \`.xlsx\` for analysis / roadmap / permutations

## Test plan
- [ ] Reviewer: \`pytest -q\` — expect 166+ passed
- [ ] Reviewer: \`python localization/run_analysis.py --help\` — expect \`--no-sheets\` flag
- [ ] Phase В will verify Phase 2/3 end-to-end on live WB API

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Acceptance criteria этого плана

- [ ] `pytest -q` → ≥166 passed (157 baseline + 9 writer tests), 0 failed
- [ ] `grep GOOGLE_CREDENTIALS_JSON` в `*.py` → пусто
- [ ] `grep localization.sheets` в `*.py` → пусто
- [ ] `localization/output/writer.py` существует с `Writer` Protocol, `SheetsWriter`, `ExcelWriter`, `make_writer()`
- [ ] Все три раннера принимают `--no-sheets` флаг
- [ ] `cabinets.yaml` имеет `sheet_id: ""` для обоих кабинетов
- [ ] `.gitignore` содержит `localization/data/output/`
- [ ] PR `feat/phase-b-excel-writer` готов к мерджу

После мерджа этого плана — следующий: **Фаза В — E2E проверка Phase 2/3 локализации** (запуск live на WB API + integration-тесты).
