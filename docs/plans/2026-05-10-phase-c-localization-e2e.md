# Phase В: Localization Phase 2/3 E2E + integration tests — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** убедиться, что `run_roadmap.py` и `run_permutations.py` работают end-to-end на живом WB API. Зафиксировать поведение интеграционными тестами с моками внешних вызовов (по образцу `tests/audit/test_run_audit.py`).

**Architecture:** Извлекаем тело `main()` каждого раннера в чистую функцию `run_roadmap(cabinet_name, ...)` / `run_permutations(cabinet_name, ...)` — по образцу `audit/run_audit.py:run_audit()`. Это даёт тестируемый entry point. Затем live E2E на OOO: если вылезут API-shape сюрпризы (как было с `warehouse_remains`/`cards/list`) — чиним atomic-коммитами в `shared/wb_api/*` или калькуляторах. Финал — интеграционные тесты с моками `load_cache`, `WBClient`, всех `fetch_*` и калькуляторов на верхнем уровне.

**Tech Stack:** Python 3.11+, pytest, openpyxl, gspread (опц.). Никаких новых зависимостей.

**Spec:** [docs/specs/2026-05-09-finalize-v1-design.md](../specs/2026-05-09-finalize-v1-design.md) §5 Фаза В.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `localization/run_roadmap.py` | Modify | extract `_parse_args()` + `run_roadmap(...)` |
| `localization/run_permutations.py` | Modify | extract `_parse_args()` + `run_permutations(...)` |
| `tests/localization/test_run_roadmap.py` | Create | integration test |
| `tests/localization/test_run_permutations.py` | Create | integration test |

**Conditional (Task 3):**
- `shared/wb_api/*` — atomic fixes по факту обнаружения API-shape проблем
- `localization/calculators/*` — то же

**Не трогаем:**
- `localization/run_analysis.py` — Phase 1 уже верифицирован на OOO; integration test для него выходит за scope Фазы В
- `audit/*` — отдельный мир
- `localization/output/*` — Фаза Б закрыла, не возвращаемся

---

## Branch Setup

- [ ] **Step 0.1: Создать ветку из main**

```bash
cd ~/Projects/wb-logistics-toolkit
git checkout main
git pull --ff-only
git status                                    # clean
git log --oneline -3                          # ожидаем de668d3 (Phase Б merge)
git checkout -b feat/phase-c-localization-e2e
```

- [ ] **Step 0.2: Baseline pytest**

```bash
.venv/bin/pytest -q
```

Expected: 166 passed, 0 failed.

---

## Task 1: Extract `run_roadmap()` from `main()`

**Files:**
- Modify: `localization/run_roadmap.py`

**Цель:** превратить `main()` в тонкую обёртку над testable-функцией. Без изменения внешнего поведения.

- [ ] **Step 1.1: Извлечь `_parse_args()` из `main()`**

В верхней части модуля (между импортами и `main()`) добавить:

```python
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WB Localization Phase 2: 13-week roadmap")
    parser.add_argument("cabinet", help="Cabinet name from cabinets.yaml")
    parser.add_argument("--target", type=float, default=85.0,
                        help="Target localization %% (default: 85)")
    parser.add_argument("--limit", type=float, default=0.3,
                        help="Realistic slot fraction (default: 0.3)")
    parser.add_argument(
        "--no-sheets",
        action="store_true",
        help="Force Excel output even if Sheets is configured",
    )
    return parser.parse_args(argv)
```

В `main()` соответствующий блок argparse удалить, заменить на:

```python
def main() -> None:
    args = _parse_args()
    run_roadmap(
        cabinet_name=args.cabinet,
        target=args.target,
        limit=args.limit,
        no_sheets=args.no_sheets,
    )
```

- [ ] **Step 1.2: Извлечь `run_roadmap(...)` из `main()`**

Между `_parse_args()` и `main()` добавить:

```python
def run_roadmap(
    cabinet_name: str,
    target: float = 85.0,
    limit: float = 0.3,
    no_sheets: bool = False,
    output_dir: str = "localization/data/output",
) -> str | None:
    """Run Phase 2 roadmap simulation.

    Returns:
        Path to Excel file if Excel-fallback was chosen, else None (Sheets path).
    """
    cache = load_cache(cabinet_name)
    if cache is None:
        print(f"ERROR: No cache for '{cabinet_name}'. Run run_analysis.py first.")
        sys.exit(1)

    cabinet = get_cabinet(cabinet_name)
    client = WBClient(token=cabinet.wb_token)
    warehouse_statuses = load_warehouse_statuses()

    redistribution_limits = {
        name: ws.redistribution_limit_per_day
        for name, ws in warehouse_statuses.items()
        if ws.available
    }

    il_irp = cache["il_irp"]
    logistics_costs = cache["logistics_costs"]
    period_days = cache["period_days"]
    articles = il_irp["articles"]

    print(f"[Phase 2] Cabinet: {cabinet_name} | Target: {target}% | "
          f"Period: {period_days}d | Articles: {len(articles)}")

    print("  Fetching warehouse remains for movement planning...")
    warehouse_remains = fetch_warehouse_remains(client)
    print(f"  Remains rows: {len(warehouse_remains)}")

    print("  Generating movements...")
    perm_result = generate_movements(
        articles, warehouse_remains, warehouse_statuses, period_days=period_days
    )
    movements = perm_result["movements"]
    print(f"  Movements: {len(movements)}")

    fd_stocks = _aggregate_stocks_by_fd(warehouse_remains)
    for art in articles:
        art_lower = art["article"].lower()
        art["stock_total"] = sum(fd_stocks.get(art_lower, {}).values())

    print("  Simulating 13-week roadmap...")
    roadmap_result = simulate_roadmap(
        articles=articles,
        movements=movements,
        logistics_costs=logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=limit,
        target_localization=target,
        period_days=period_days,
    )

    milestones = roadmap_result["milestones"]
    print(f"  Week 60%: {milestones['week_60pct']}  Week 80%: {milestones['week_80pct']}")

    from localization.output.writer import SheetsWriter, make_writer
    from localization.output.roadmap_writer import write_roadmap

    excel_path = f"{output_dir}/Локализация Roadmap {cabinet_name}.xlsx"
    try:
        writer = make_writer(
            sheet_id=cabinet.sheet_id,
            excel_path=excel_path,
            force_excel=no_sheets,
        )
        write_roadmap(writer, roadmap_result)
        out = writer.finalize()
        if isinstance(writer, SheetsWriter):
            print(f"  Sheets updated: {cabinet.sheet_id}")
            return None
        print(f"  Excel saved: {out}")
        return out
    except Exception as exc:
        print(f"  Output failed (non-fatal): {exc}")
        return None
```

После рефакторинга весь блок-внутренности из старого `main()` (от `cache = load_cache(...)` до `print("  Output failed ...")`) уже находится в `run_roadmap()`. В `main()` остаётся только Step 1.1's короткий вызов.

- [ ] **Step 1.3: Sanity — модуль импортируется, `--help` работает**

```bash
.venv/bin/python -c "from localization.run_roadmap import _parse_args, run_roadmap; print('OK')"
.venv/bin/python localization/run_roadmap.py --help
```

Expected: `OK`, затем help с `cabinet`, `--target`, `--limit`, `--no-sheets`.

- [ ] **Step 1.4: pytest baseline**

```bash
.venv/bin/pytest -q
```

Expected: 166 passed, 0 failed.

- [ ] **Step 1.5: Commit**

```bash
git add localization/run_roadmap.py
git commit -m "refactor(localization): extract run_roadmap() from main() for testability"
```

---

## Task 2: Extract `run_permutations()` from `main()`

**Files:**
- Modify: `localization/run_permutations.py`

- [ ] **Step 2.1: Извлечь `_parse_args()` из `main()`**

```python
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WB Localization Phase 3: stock permutation recommendations"
    )
    parser.add_argument("cabinet", help="Cabinet name from cabinets.yaml")
    parser.add_argument("--safety-days", type=int, default=14,
                        help="Days of stock to protect at donor (default: 14)")
    parser.add_argument(
        "--no-sheets",
        action="store_true",
        help="Force Excel output even if Sheets is configured",
    )
    return parser.parse_args(argv)
```

`main()` сжимается до:

```python
def main() -> None:
    args = _parse_args()
    run_permutations(
        cabinet_name=args.cabinet,
        safety_days=args.safety_days,
        no_sheets=args.no_sheets,
    )
```

- [ ] **Step 2.2: Извлечь `run_permutations(...)` из `main()`**

```python
def run_permutations(
    cabinet_name: str,
    safety_days: int = 14,
    no_sheets: bool = False,
    output_dir: str = "localization/data/output",
) -> str | None:
    """Run Phase 3 permutation recommendations.

    Returns:
        Path to Excel file if Excel-fallback was chosen, else None (Sheets path).
    """
    cache = load_cache(cabinet_name)
    if cache is None:
        print(f"ERROR: No cache for '{cabinet_name}'. Run run_analysis.py first.")
        sys.exit(1)

    cabinet = get_cabinet(cabinet_name)
    client = WBClient(token=cabinet.wb_token)
    warehouse_statuses = load_warehouse_statuses()

    il_irp = cache["il_irp"]
    period_days = cache["period_days"]
    articles = il_irp["articles"]

    print(f"[Phase 3] Cabinet: {cabinet_name} | Safety: {safety_days}d | "
          f"Articles: {len(articles)}")

    print("  Fetching warehouse remains...")
    warehouse_remains = fetch_warehouse_remains(client)
    print(f"  Remains rows: {len(warehouse_remains)}")

    print("  Generating movement recommendations...")
    result = generate_movements(
        articles=articles,
        warehouse_remains=warehouse_remains,
        warehouse_statuses=warehouse_statuses,
        period_days=period_days,
        safety_days=safety_days,
    )

    print(f"  Movements: {len(result['movements'])} | Supplies: {len(result['supplies'])}")
    for fd_row in result["region_summary"]:
        print(f"    {fd_row['fd']:35s}  stock={fd_row['stock_total']:5d}  "
              f"orders={fd_row['orders_total']:5d}  loc={fd_row['loc_pct']:5.1f}%")

    from localization.output.writer import SheetsWriter, make_writer
    from localization.output.permutations_writer import write_permutations

    excel_path = f"{output_dir}/Локализация Перестановки {cabinet_name}.xlsx"
    try:
        writer = make_writer(
            sheet_id=cabinet.sheet_id,
            excel_path=excel_path,
            force_excel=no_sheets,
        )
        write_permutations(writer, result)
        out = writer.finalize()
        if isinstance(writer, SheetsWriter):
            print(f"  Sheets updated: {cabinet.sheet_id}")
            return None
        print(f"  Excel saved: {out}")
        return out
    except Exception as exc:
        print(f"  Output failed (non-fatal): {exc}")
        return None
```

- [ ] **Step 2.3: Sanity**

```bash
.venv/bin/python -c "from localization.run_permutations import _parse_args, run_permutations; print('OK')"
.venv/bin/python localization/run_permutations.py --help
```

Expected: `OK`, help с `cabinet`, `--safety-days`, `--no-sheets`.

- [ ] **Step 2.4: pytest**

```bash
.venv/bin/pytest -q
```

Expected: 166 passed.

- [ ] **Step 2.5: Commit**

```bash
git add localization/run_permutations.py
git commit -m "refactor(localization): extract run_permutations() from main() for testability"
```

---

## Task 3: Live E2E на OOO — Phase 1 cache refresh + Phase 2 + Phase 3

**Files:**
- (потенциальные fix-файлы) `shared/wb_api/*`, `localization/calculators/*`

**Цель:** прогнать всю цепочку на живом WB API кабинета OOO, поймать любые API-shape сюрпризы. Это exploratory-таск: 0..N atomic-коммитов с фиксами, в зависимости от того, что найдём.

**Pre-flight:** в `.env` должен быть валидный `WB_TOKEN_OOO` (Статистика + Контент + Аналитика + Тарифы). Проверка:

```bash
.venv/bin/python check_setup.py
```

Expected: 7/7 ✅. Если ❌ на токене — STOP и запросить у user'а свежий токен.

- [ ] **Step 3.1: Phase 1 — refresh кэша OOO (нужен Phase 2/3)**

```bash
.venv/bin/python localization/run_analysis.py ooo --days 60 --no-sheets
```

Expected:
- exit 0
- сообщение `Cache saved → localization/data/cache/ooo_latest.json`
- сообщение `Excel saved: localization/data/output/Локализация Анализ ooo.xlsx`
- файл `.xlsx` существует и открывается openpyxl без ошибок:

```bash
.venv/bin/python -c "
from openpyxl import load_workbook
wb = load_workbook('localization/data/output/Локализация Анализ ooo.xlsx')
print('Sheets:', wb.sheetnames)
"
```

Если падение — диагностика по traceback'у. Типичные виновники: `fetch_orders`, `fetch_warehouse_remains`, `fetch_card_dimensions`, `fetch_report`. Чинить atomic-коммитом в `shared/wb_api/<endpoint>.py`. После фикса — повторить Step 3.1.

- [ ] **Step 3.2: Phase 2 — roadmap**

```bash
.venv/bin/python localization/run_roadmap.py ooo --target 85 --no-sheets
```

Expected:
- exit 0
- `Remains rows: N` (N > 0)
- `Movements: M` (M ≥ 0 — ноль допустим, если уже всё локализовано)
- `Week 60%: X  Week 80%: Y` (числа или `None`)
- `Excel saved: localization/data/output/Локализация Roadmap ooo.xlsx`

Проверка файла:

```bash
.venv/bin/python -c "
from openpyxl import load_workbook
wb = load_workbook('localization/data/output/Локализация Roadmap ooo.xlsx')
ws = wb['Роадмап 13 нед.']
print('Sheets:', wb.sheetnames)
print('Rows:', ws.max_row)
"
```

Expected: `Sheets: ['Роадмап 13 нед.']`, `Rows: ≥ 14` (~10 мета-строк + 13 недель + header).

При падении — atomic fix (см. Step 3.1).

- [ ] **Step 3.3: Phase 3 — permutations**

```bash
.venv/bin/python localization/run_permutations.py ooo --no-sheets
```

Expected:
- exit 0
- блок `region_summary` с 8 строками ФО (или сколько активных warehouse_statuses)
- `Excel saved: localization/data/output/Локализация Перестановки ooo.xlsx`

Проверка файла:

```bash
.venv/bin/python -c "
from openpyxl import load_workbook
wb = load_workbook('localization/data/output/Локализация Перестановки ooo.xlsx')
print('Sheets:', wb.sheetnames)
"
```

Expected: 4 листа — `['Перемещения', 'Допоставки', 'Сводка регионов', 'Обновление']`.

При падении — atomic fix.

- [ ] **Step 3.4: Если были фиксы — финальный pytest**

```bash
.venv/bin/pytest -q
```

Expected: 166 passed, 0 failed (после любого фикса WB API клиента или калькулятора tests должны оставаться зелёными; если фикс сломал юнит-тест — обновить тест в том же commit'е).

- [ ] **Step 3.5: Acceptance**

Для completion этого таска требуется ВСЕ:
- Step 3.1 / 3.2 / 3.3 прошли с exit 0
- 3 файла `.xlsx` существуют и открываются openpyxl без ошибок
- pytest 166 passed (баг-фиксы, если были, не сломали юнит-тесты)
- если были фиксы — каждый отдельным atomic-коммитом с описанием root cause

Если Steps 3.1-3.3 не сходятся за **3 итерации фикса** — BLOCKED, escalate (root cause не очевиден или меняется WB API спека).

> **Важно:** `localization/data/output/*.xlsx` находятся в `.gitignore` (Phase Б, Step 8.2). Артефакты не коммитятся — они существуют локально как evidence.

---

## Task 4: Integration test для `run_roadmap`

**Files:**
- Create: `tests/localization/test_run_roadmap.py`

- [ ] **Step 4.1: Failing test**

Создать `tests/localization/test_run_roadmap.py`:

```python
from unittest.mock import MagicMock, patch
from pathlib import Path

from localization.run_roadmap import _parse_args, run_roadmap


def test_parse_args_basic():
    args = _parse_args(["ooo"])
    assert args.cabinet == "ooo"
    assert args.target == 85.0
    assert args.limit == 0.3
    assert args.no_sheets is False


def test_parse_args_with_target_and_no_sheets():
    args = _parse_args(["ooo", "--target", "90", "--limit", "0.5", "--no-sheets"])
    assert args.cabinet == "ooo"
    assert args.target == 90.0
    assert args.limit == 0.5
    assert args.no_sheets is True


def test_run_roadmap_returns_excel_path_when_no_sheets(tmp_path):
    fake_cache = {
        "il_irp": {
            "articles": [
                {"article": "X", "wb_local": 50, "wb_total": 100, "loc_pct": 50.0,
                 "ktr": 0.7, "krp_pct": 70.0},
            ],
        },
        "logistics_costs": {"total_monthly": 1000.0},
        "period_days": 60,
    }
    fake_cabinet = MagicMock(wb_token="tok", sheet_id="")
    fake_roadmap = {
        "milestones": {"week_60pct": 5, "week_80pct": 10},
        "params": {"target_localization": 85, "realistic_limit_pct": 0.3},
        "roadmap": [{"week": 1, "date": "2026-05-12"}],
    }
    fake_perm = {"movements": []}

    with patch("localization.run_roadmap.load_cache", return_value=fake_cache), \
         patch("localization.run_roadmap.get_cabinet", return_value=fake_cabinet), \
         patch("localization.run_roadmap.WBClient"), \
         patch("localization.run_roadmap.load_warehouse_statuses", return_value={}), \
         patch("localization.run_roadmap.fetch_warehouse_remains", return_value=[]), \
         patch("localization.run_roadmap.generate_movements", return_value=fake_perm), \
         patch("localization.run_roadmap.simulate_roadmap", return_value=fake_roadmap):
        path = run_roadmap(
            cabinet_name="ooo",
            no_sheets=True,
            output_dir=str(tmp_path),
        )

    assert path is not None
    assert "Roadmap" in path
    assert path.endswith(".xlsx")
    assert Path(path).exists()


def test_run_roadmap_exits_when_no_cache(tmp_path):
    import pytest
    with patch("localization.run_roadmap.load_cache", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            run_roadmap(
                cabinet_name="missing",
                no_sheets=True,
                output_dir=str(tmp_path),
            )
        assert exc_info.value.code == 1
```

- [ ] **Step 4.2: Run — should pass (рефактор Task 1 уже даёт нужный API)**

```bash
.venv/bin/pytest tests/localization/test_run_roadmap.py -v
```

Expected: 4 passed.

Если падает с `ImportError` или `AttributeError` — рефактор Task 1 неполный, вернуться. Если падает с реальной ошибкой логики — фиксить либо runner, либо тест (root cause диктует).

- [ ] **Step 4.3: Полный pytest**

```bash
.venv/bin/pytest -q
```

Expected: 170 passed (166 + 4 новых).

- [ ] **Step 4.4: Commit**

```bash
git add tests/localization/test_run_roadmap.py
git commit -m "test(localization): integration test for run_roadmap"
```

---

## Task 5: Integration test для `run_permutations`

**Files:**
- Create: `tests/localization/test_run_permutations.py`

- [ ] **Step 5.1: Failing test**

```python
from unittest.mock import MagicMock, patch
from pathlib import Path

from localization.run_permutations import _parse_args, run_permutations


def test_parse_args_basic():
    args = _parse_args(["ooo"])
    assert args.cabinet == "ooo"
    assert args.safety_days == 14
    assert args.no_sheets is False


def test_parse_args_with_safety_and_no_sheets():
    args = _parse_args(["ooo", "--safety-days", "7", "--no-sheets"])
    assert args.cabinet == "ooo"
    assert args.safety_days == 7
    assert args.no_sheets is True


def test_run_permutations_returns_excel_path_when_no_sheets(tmp_path):
    fake_cache = {
        "il_irp": {
            "articles": [
                {"article": "X", "wb_local": 50, "wb_total": 100, "loc_pct": 50.0},
            ],
        },
        "period_days": 60,
    }
    fake_cabinet = MagicMock(wb_token="tok", sheet_id="")
    fake_result = {
        "movements": [{"article": "X", "from_fd": "ЦФО", "from_warehouse": "Коледино",
                       "to_fd": "СЗФО", "to_warehouse": "СПб", "qty": 10}],
        "supplies": [],
        "region_summary": [
            {"fd": "ЦФО", "stock_total": 100, "orders_total": 50, "loc_pct": 80.0}
        ],
    }

    with patch("localization.run_permutations.load_cache", return_value=fake_cache), \
         patch("localization.run_permutations.get_cabinet", return_value=fake_cabinet), \
         patch("localization.run_permutations.WBClient"), \
         patch("localization.run_permutations.load_warehouse_statuses", return_value={}), \
         patch("localization.run_permutations.fetch_warehouse_remains", return_value=[]), \
         patch("localization.run_permutations.generate_movements", return_value=fake_result):
        path = run_permutations(
            cabinet_name="ooo",
            no_sheets=True,
            output_dir=str(tmp_path),
        )

    assert path is not None
    assert "Перестановки" in path
    assert path.endswith(".xlsx")
    assert Path(path).exists()


def test_run_permutations_exits_when_no_cache(tmp_path):
    import pytest
    with patch("localization.run_permutations.load_cache", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            run_permutations(
                cabinet_name="missing",
                no_sheets=True,
                output_dir=str(tmp_path),
            )
        assert exc_info.value.code == 1
```

- [ ] **Step 5.2: Run**

```bash
.venv/bin/pytest tests/localization/test_run_permutations.py -v
```

Expected: 4 passed.

- [ ] **Step 5.3: Полный pytest**

```bash
.venv/bin/pytest -q
```

Expected: 174 passed (170 + 4).

- [ ] **Step 5.4: Commit**

```bash
git add tests/localization/test_run_permutations.py
git commit -m "test(localization): integration test for run_permutations"
```

---

## Task 6: Final sanity + PR

- [ ] **Step 6.1: Финальный pytest и проверки**

```bash
.venv/bin/pytest -q
```

Expected: ≥174 passed, 0 failed.

```bash
.venv/bin/python check_setup.py
```

Expected: 7/7 ✅.

```bash
.venv/bin/python localization/run_roadmap.py --help | grep -E "no-sheets|target|limit"
.venv/bin/python localization/run_permutations.py --help | grep -E "no-sheets|safety-days"
```

Expected: оба help'а показывают свои флаги.

- [ ] **Step 6.2: Push + PR**

```bash
git push -u origin feat/phase-c-localization-e2e
gh pr create --title "Phase В: localization Phase 2/3 E2E + integration tests" --body "$(cat <<'EOF'
## Summary
- Extract `run_roadmap()` from `main()` in `localization/run_roadmap.py` (testable entry point, mirrors `audit/run_audit.py`).
- Extract `run_permutations()` from `main()` in `localization/run_permutations.py`.
- Live E2E на OOO: Phase 1 (cache refresh) → Phase 2 → Phase 3 — все три выдают валидные `.xlsx`.
- Integration tests: `tests/localization/test_run_roadmap.py` и `test_run_permutations.py` (по образцу `tests/audit/test_run_audit.py`).
- (если были API-shape фиксы по ходу live-прогона — перечислить их здесь по коммитам)

## Plan / Spec
- Spec: `docs/specs/2026-05-09-finalize-v1-design.md` §5 Фаза В
- Plan: `docs/plans/2026-05-10-phase-c-localization-e2e.md`

## Acceptance
- [x] pytest ≥ 174 passed (166 baseline + 4 roadmap + 4 permutations), 0 failed
- [x] `_parse_args` и `run_roadmap` / `run_permutations` экспортируются как функции
- [x] Live E2E OOO: 3 файла `.xlsx` валидны (Phase 1 + Phase 2 + Phase 3)
- [x] Phase 2 file: `Роадмап 13 нед.` с ≥14 строк
- [x] Phase 3 file: 4 листа (`Перемещения`, `Допоставки`, `Сводка регионов`, `Обновление`)

## Test plan
- [ ] Reviewer: `pytest -q` — expect ≥174 passed
- [ ] Phase Г будет деплоить cron-collector тарифов на app server

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Acceptance criteria этого плана

- [ ] `pytest -q` → ≥174 passed (166 baseline + 4 roadmap + 4 permutations), 0 failed
- [ ] `localization/run_roadmap.py` имеет `_parse_args()` и `run_roadmap()` как top-level функции
- [ ] `localization/run_permutations.py` имеет `_parse_args()` и `run_permutations()` как top-level функции
- [ ] Live E2E на OOO: 3 валидных `.xlsx` файла на диске (Phase 1 + 2 + 3)
- [ ] PR `feat/phase-c-localization-e2e` готов к мерджу

После мерджа этого плана — следующий: **Фаза Г — Cron на app server + мониторинг + backup** (deploy на timeweb, tariff_collector × 2 кабинета по cron, Telegram-алерты, weekly backup БД).
