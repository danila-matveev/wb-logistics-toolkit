#!/usr/bin/env python3
"""Phase 1: Fetch WB orders + report → analyze ИЛ/ИРП → cache + Sheets.

Usage:
    python localization/run_analysis.py <cabinet> [--days 30]

Example:
    python localization/run_analysis.py MAIN --days 30
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import get_cabinet, load_warehouse_statuses
from shared.wb_api.client import WBClient
from shared.wb_api.orders import fetch_orders
from shared.wb_api.reports import fetch_report
from localization.calculators.il_irp_analyzer import analyze_il_irp
from localization.calculators.scenario_engine import analyze_scenarios
from localization.data.cache import save_cache


def _build_prices_dict(report_rows: list[dict[str, Any]]) -> dict[str, float]:
    """article_lower → max retail_price seen in report rows."""
    prices: dict[str, float] = {}
    for row in report_rows:
        article = (row.get("sa_name") or "").lower()
        price = float(row.get("retail_price") or 0)
        if article and price > 0:
            prices[article] = max(prices.get(article, 0.0), price)
    return prices


def _build_logistics_costs(report_rows: list[dict[str, Any]]) -> dict[str, float]:
    """article_lower → total delivery_rub in period."""
    costs: dict[str, float] = {}
    for row in report_rows:
        article = (row.get("sa_name") or "").lower()
        delivery = float(row.get("delivery_rub") or 0)
        if article:
            costs[article] = costs.get(article, 0.0) + delivery
    return costs


def _calc_turnover(report_rows: list[dict[str, Any]]) -> float:
    return sum(float(r.get("retail_amount") or 0) for r in report_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="WB Localization Phase 1: ИЛ/ИРП analysis")
    parser.add_argument("cabinet", help="Cabinet name from cabinets.yaml (e.g. MAIN)")
    parser.add_argument("--days", type=int, default=30, help="Analysis period in days (default: 30)")
    parser.add_argument(
        "--no-sheets",
        action="store_true",
        help="Force Excel output even if Sheets is configured",
    )
    args = parser.parse_args()

    cabinet = get_cabinet(args.cabinet)
    client = WBClient(token=cabinet.wb_token)

    date_to = date.today()
    date_from = date_to - timedelta(days=args.days)

    print(f"[Phase 1] Cabinet: {args.cabinet} | Period: {date_from} → {date_to}")

    print("  Fetching orders...")
    orders = fetch_orders(
        client,
        date_from=date_from.isoformat(),
        exclude_cancelled=False,
    )
    print(f"  Orders: {len(orders)}")

    print("  Fetching report (logistics costs)...")
    report_rows = fetch_report(
        client,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
    )
    print(f"  Report rows: {len(report_rows)}")

    prices = _build_prices_dict(report_rows)
    logistics_costs = _build_logistics_costs(report_rows)
    turnover = _calc_turnover(report_rows)

    print("  Analyzing ИЛ/ИРП...")
    il_irp = analyze_il_irp(orders, prices, period_days=args.days)
    summary = il_irp["summary"]
    print(f"  IL={summary['overall_il']:.3f}  loc%={summary['loc_pct']:.1f}%  "
          f"articles={summary['total_articles']}")

    print("  Analyzing scenarios...")
    scenarios = analyze_scenarios(
        il_irp, logistics_costs, turnover_rub=turnover, period_days=args.days
    )

    cache_payload = {
        "cabinet": args.cabinet,
        "period_days": args.days,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "il_irp": il_irp,
        "scenarios": scenarios,
        "logistics_costs": logistics_costs,
    }
    save_cache(args.cabinet, cache_payload)
    print(f"  Cache saved → localization/data/cache/{args.cabinet}_latest.json")

    from localization.output.writer import SheetsWriter, make_writer
    from localization.output.analysis_writer import write_analysis

    excel_path = f"localization/data/output/Локализация Анализ {args.cabinet}.xlsx"
    try:
        writer = make_writer(
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


if __name__ == "__main__":
    main()
