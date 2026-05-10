"""Daily ETL: fetch WB box tariffs → upsert into local SQLite wb_tariffs.

Usage:
    python audit/etl/tariff_collector.py                    # today, ooo cabinet
    python audit/etl/tariff_collector.py --date 2026-03-20
    python audit/etl/tariff_collector.py --backfill 30
    python audit/etl/tariff_collector.py --cabinet ip
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.config import get_cabinet
from shared.db import get_connection
from shared.wb_api.client import WBClient
from shared.wb_api.tariffs import fetch_box_tariffs
from audit.models.tariff_snapshot import TariffSnapshot

logger = logging.getLogger(__name__)


def build_upsert_rows(dt: date, raw_tariffs: list[dict]) -> list[dict]:
    """Convert raw API tariff list to upsert dicts."""
    rows = []
    for d in raw_tariffs:
        snap = TariffSnapshot.from_api(d)
        rows.append({
            "dt": dt.isoformat(),
            "warehouse_name": snap.warehouse_name,
            "delivery_coef": snap.delivery_coef_pct,
            "logistics_1l": snap.box_delivery_base,
            "logistics_extra_l": snap.box_delivery_liter,
            "box_storage_base": snap.box_storage_base,
            "storage_coef": snap.storage_coef_pct,
            "geo_name": snap.geo_name,
        })
    return rows


_UPSERT_SQL = """
INSERT INTO wb_tariffs (
    dt, warehouse_name, delivery_coef, logistics_1l, logistics_extra_l,
    box_storage_base, storage_coef, geo_name
) VALUES (
    :dt, :warehouse_name, :delivery_coef, :logistics_1l, :logistics_extra_l,
    :box_storage_base, :storage_coef, :geo_name
)
ON CONFLICT(dt, warehouse_name) DO UPDATE SET
    delivery_coef     = excluded.delivery_coef,
    logistics_1l      = excluded.logistics_1l,
    logistics_extra_l = excluded.logistics_extra_l,
    box_storage_base  = excluded.box_storage_base,
    storage_coef      = excluded.storage_coef,
    geo_name          = excluded.geo_name,
    created_at        = datetime('now')
"""


def collect_tariffs(dt: date, cabinet_name: str) -> int:
    """Fetch tariffs for a single date and upsert into SQLite. Returns row count."""
    cab = get_cabinet(cabinet_name)
    client = WBClient(token=cab.wb_token)
    raw = fetch_box_tariffs(client, dt.isoformat())
    if not raw:
        logger.warning("No tariffs returned for %s", dt)
        return 0

    rows = build_upsert_rows(dt, raw)
    conn = get_connection()
    conn.executemany(_UPSERT_SQL, rows)
    conn.commit()
    logger.info("Upserted %d warehouse tariffs for %s", len(rows), dt)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="WB Tariff Collector → SQLite")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--backfill", type=int, default=None, help="Backfill last N days")
    parser.add_argument("--cabinet", type=str, default="ooo")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.backfill:
        total = 0
        for i in range(args.backfill):
            dt = date.today() - timedelta(days=i)
            total += collect_tariffs(dt, args.cabinet)
        logger.info("Backfill complete: %d total rows across %d days", total, args.backfill)
    else:
        dt = date.fromisoformat(args.date) if args.date else date.today()
        collect_tariffs(dt, args.cabinet)


if __name__ == "__main__":
    main()
