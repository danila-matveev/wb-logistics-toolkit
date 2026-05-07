"""Write Phase 3 (permutation recommendations) to Google Sheets."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import gspread

from shared.sheets_client import clear_and_write, get_or_create_worksheet, to_number


def write_permutations(
    spreadsheet: gspread.Spreadsheet,
    permutation_result: dict[str, Any],
) -> None:
    """Write generate_movements() output to four sheets.

    Sheets: "Перемещения", "Допоставки", "Сводка регионов", "Обновление".
    """
    _write_movements(spreadsheet, permutation_result.get("movements", []))
    _write_supplies(spreadsheet, permutation_result.get("supplies", []))
    _write_region_summary(spreadsheet, permutation_result.get("region_summary", []))
    _write_update_timestamp(spreadsheet)


def _write_movements(
    spreadsheet: gspread.Spreadsheet,
    movements: list[dict[str, Any]],
) -> None:
    ws = get_or_create_worksheet(spreadsheet, "Перемещения")
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
    clear_and_write(ws, rows)


def _write_supplies(
    spreadsheet: gspread.Spreadsheet,
    supplies: list[dict[str, Any]],
) -> None:
    ws = get_or_create_worksheet(spreadsheet, "Допоставки")
    header = ["Артикул", "Куда ФО", "Куда склад", "Кол-во шт"]
    rows = [header]
    for s in supplies:
        rows.append([
            s.get("article", ""),
            s.get("to_fd", ""),
            s.get("to_warehouse", ""),
            to_number(s.get("qty", 0)),
        ])
    clear_and_write(ws, rows)


def _write_region_summary(
    spreadsheet: gspread.Spreadsheet,
    region_summary: list[dict[str, Any]],
) -> None:
    ws = get_or_create_worksheet(spreadsheet, "Сводка регионов")
    header = ["ФО", "Остатки шт", "Заказов шт", "Лок. %"]
    rows = [header]
    for r in region_summary:
        rows.append([
            r.get("fd", ""),
            to_number(r.get("stock_total", 0)),
            to_number(r.get("orders_total", 0)),
            to_number(r.get("loc_pct", 0)),
        ])
    clear_and_write(ws, rows)


def _write_update_timestamp(spreadsheet: gspread.Spreadsheet) -> None:
    ws = get_or_create_worksheet(spreadsheet, "Обновление")
    clear_and_write(ws, [
        ["Обновлено", datetime.now().strftime("%d.%m.%Y %H:%M")],
        ["Источник", "WB API (warehouse/remains + supplier/orders + reportDetailByPeriod)"],
    ])
