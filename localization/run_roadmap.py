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


def main() -> None:
    parser = argparse.ArgumentParser(description="WB Localization Phase 2: 13-week roadmap")
    parser.add_argument("cabinet", help="Cabinet name from cabinets.yaml")
    parser.add_argument("--target", type=float, default=85.0,
                        help="Target localization %% (default: 85)")
    parser.add_argument("--limit", type=float, default=0.3,
                        help="Realistic slot fraction (default: 0.3)")
    args = parser.parse_args()

    cache = load_cache(args.cabinet)
    if cache is None:
        print(f"ERROR: No cache for '{args.cabinet}'. Run run_analysis.py first.")
        sys.exit(1)

    cabinet = get_cabinet(args.cabinet)
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

    print(f"[Phase 2] Cabinet: {args.cabinet} | Target: {args.target}% | "
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
        realistic_limit_pct=args.limit,
        target_localization=args.target,
        period_days=period_days,
    )

    milestones = roadmap_result["milestones"]
    print(f"  Week 60%: {milestones['week_60pct']}  Week 80%: {milestones['week_80pct']}")

    try:
        import os
        if not os.environ.get("GOOGLE_CREDENTIALS_JSON"):
            print("  Sheets: GOOGLE_CREDENTIALS_JSON not set, skipping.")
            return
        from shared.sheets_client import get_client
        from localization.sheets.roadmap_writer import write_roadmap
        gc = get_client()
        spreadsheet = gc.open_by_key(cabinet.sheet_id)
        write_roadmap(spreadsheet, roadmap_result)
        print(f"  Sheets updated: {cabinet.sheet_id}")
    except Exception as exc:
        print(f"  Sheets export failed (non-fatal): {exc}")


if __name__ == "__main__":
    main()
