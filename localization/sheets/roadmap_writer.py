"""Write Phase 2 (13-week roadmap) to Google Sheets."""
from __future__ import annotations

from typing import Any

import gspread

from shared.sheets_client import clear_and_write, get_or_create_worksheet, to_number


def write_roadmap(
    spreadsheet: gspread.Spreadsheet,
    roadmap_result: dict[str, Any],
) -> None:
    """Write simulate_roadmap() output to sheet "Роадмап 13 нед."."""
    ws = get_or_create_worksheet(spreadsheet, "Роадмап 13 нед.")
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

    clear_and_write(ws, meta_rows + data_rows)
