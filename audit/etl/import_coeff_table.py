"""Bootstrap wb_coeff_table in Supabase with current WB КТР/КРП coefficients.

Usage:
    python audit/etl/import_coeff_table.py                    # use default valid_from
    python audit/etl/import_coeff_table.py --valid-from 2026-03-27
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.supabase import get_supabase_client

logger = logging.getLogger(__name__)

# KTR/KRP table effective from 27.03.2026 (source: WB Partners → Тарифы)
COEFF_TABLE: list[dict] = [
    {"min_loc": 95.00, "max_loc": 100.00, "ktr": 0.50, "krp_pct": 0.00},
    {"min_loc": 90.00, "max_loc":  94.99, "ktr": 0.60, "krp_pct": 0.00},
    {"min_loc": 85.00, "max_loc":  89.99, "ktr": 0.70, "krp_pct": 0.00},
    {"min_loc": 80.00, "max_loc":  84.99, "ktr": 0.80, "krp_pct": 0.00},
    {"min_loc": 75.00, "max_loc":  79.99, "ktr": 0.90, "krp_pct": 0.00},
    {"min_loc": 70.00, "max_loc":  74.99, "ktr": 1.00, "krp_pct": 0.00},
    {"min_loc": 65.00, "max_loc":  69.99, "ktr": 1.00, "krp_pct": 0.00},
    {"min_loc": 60.00, "max_loc":  64.99, "ktr": 1.00, "krp_pct": 0.00},
    {"min_loc": 55.00, "max_loc":  59.99, "ktr": 1.05, "krp_pct": 2.00},
    {"min_loc": 50.00, "max_loc":  54.99, "ktr": 1.10, "krp_pct": 2.05},
    {"min_loc": 45.00, "max_loc":  49.99, "ktr": 1.20, "krp_pct": 2.05},
    {"min_loc": 40.00, "max_loc":  44.99, "ktr": 1.30, "krp_pct": 2.10},
    {"min_loc": 35.00, "max_loc":  39.99, "ktr": 1.40, "krp_pct": 2.10},
    {"min_loc": 30.00, "max_loc":  34.99, "ktr": 1.60, "krp_pct": 2.15},
    {"min_loc": 25.00, "max_loc":  29.99, "ktr": 1.70, "krp_pct": 2.20},
    {"min_loc": 20.00, "max_loc":  24.99, "ktr": 1.80, "krp_pct": 2.25},
    {"min_loc": 15.00, "max_loc":  19.99, "ktr": 1.90, "krp_pct": 2.30},
    {"min_loc": 10.00, "max_loc":  14.99, "ktr": 2.00, "krp_pct": 2.35},
    {"min_loc":  5.00, "max_loc":   9.99, "ktr": 2.10, "krp_pct": 2.45},
    {"min_loc":  0.00, "max_loc":   4.99, "ktr": 2.20, "krp_pct": 2.50},
]

DEFAULT_VALID_FROM = "2026-03-27"


def import_coeff_table(valid_from: str = DEFAULT_VALID_FROM) -> int:
    """Upsert COEFF_TABLE into wb_coeff_table with the given valid_from date.

    Returns number of rows upserted.
    """
    client = get_supabase_client()
    rows = [{"valid_from": valid_from, **row} for row in COEFF_TABLE]
    result = (
        client.table("wb_coeff_table")
        .upsert(rows, on_conflict="valid_from,min_loc")
        .execute()
    )
    count = len(result.data or [])
    logger.info("Upserted %d KTR/KRP rows with valid_from=%s", count, valid_from)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap wb_coeff_table in Supabase")
    parser.add_argument("--valid-from", type=str, default=DEFAULT_VALID_FROM)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    count = import_coeff_table(args.valid_from)
    print(f"Done: {count} rows upserted")


if __name__ == "__main__":
    main()
