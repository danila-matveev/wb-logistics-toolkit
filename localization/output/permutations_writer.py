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
