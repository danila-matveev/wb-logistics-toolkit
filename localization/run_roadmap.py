#!/usr/bin/env python3
"""Phase 2: Load Phase 1 cache → simulate 13-week roadmap → Sheets.

Usage:
    python localization/run_roadmap.py <cabinet> [--target 85] [--limit 0.3]

Example:
    python localization/run_roadmap.py MAIN --target 85
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import get_cabinet, load_warehouse_statuses
from shared.wb_api.client import WBClient
from shared.wb_api.warehouse_remains import fetch_warehouse_remains
from localization.data.cache import load_cache
from localization.calculators.relocation_forecaster import simulate_roadmap
from localization.permutation_calculator import generate_movements, _aggregate_stocks_by_fd


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

    # Enrich articles with stock_total from warehouse_remains for accurate move_fraction.
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


def main() -> None:
    args = _parse_args()
    run_roadmap(
        cabinet_name=args.cabinet,
        target=args.target,
        limit=args.limit,
        no_sheets=args.no_sheets,
    )


if __name__ == "__main__":
    main()
