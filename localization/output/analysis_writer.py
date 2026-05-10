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
