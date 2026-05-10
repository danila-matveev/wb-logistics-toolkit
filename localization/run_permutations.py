#!/usr/bin/env python3
"""Phase 3: Load cache + fetch warehouse_remains → generate permutations → Sheets.

Usage:
    python localization/run_permutations.py <cabinet> [--safety-days 14]

Example:
    python localization/run_permutations.py MAIN
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
from localization.permutation_calculator import generate_movements


def main() -> None:
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
    args = parser.parse_args()

    cache = load_cache(args.cabinet)
    if cache is None:
        print(f"ERROR: No cache for '{args.cabinet}'. Run run_analysis.py first.")
        sys.exit(1)

    cabinet = get_cabinet(args.cabinet)
    client = WBClient(token=cabinet.wb_token)
    warehouse_statuses = load_warehouse_statuses()

    il_irp = cache["il_irp"]
    period_days = cache["period_days"]
    articles = il_irp["articles"]

    print(f"[Phase 3] Cabinet: {args.cabinet} | Safety: {args.safety_days}d | "
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
        safety_days=args.safety_days,
    )

    print(f"  Movements: {len(result['movements'])} | Supplies: {len(result['supplies'])}")
    for fd_row in result["region_summary"]:
        print(f"    {fd_row['fd']:35s}  stock={fd_row['stock_total']:5d}  "
              f"orders={fd_row['orders_total']:5d}  loc={fd_row['loc_pct']:5.1f}%")

    from localization.output.writer import SheetsWriter, make_writer
    from localization.output.permutations_writer import write_permutations

    excel_path = f"localization/data/output/Локализация Перестановки {args.cabinet}.xlsx"
    try:
        writer = make_writer(
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


if __name__ == "__main__":
    main()
