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


def main() -> None:
    args = _parse_args()
    run_permutations(
        cabinet_name=args.cabinet,
        safety_days=args.safety_days,
        no_sheets=args.no_sheets,
    )


if __name__ == "__main__":
    main()
