#!/usr/bin/env python3
"""ONE-SHOT: migrate wb_tariffs rows from Supabase to local SQLite.

Run once when cutting over from Supabase to SQLite. Requires `supabase`
package temporarily installed AND SUPABASE_URL/SUPABASE_KEY in .env.

Usage:
    .venv/bin/pip install supabase
    python scripts/migrate_supabase_to_sqlite.py
    .venv/bin/pip uninstall -y supabase

After running, delete this script (it has no purpose post-migration).
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from shared.db import get_connection

logger = logging.getLogger(__name__)


_INSERT_SQL = """
INSERT OR REPLACE INTO wb_tariffs (
    dt, warehouse_name, delivery_coef, logistics_1l, logistics_extra_l,
    box_storage_base, storage_coef, geo_name
) VALUES (
    :dt, :warehouse_name, :delivery_coef, :logistics_1l, :logistics_extra_l,
    :box_storage_base, :storage_coef, :geo_name
)
"""


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env", file=sys.stderr)
        return 2

    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase package not installed.\n"
              "Run: .venv/bin/pip install supabase", file=sys.stderr)
        return 2

    client = create_client(url, key)
    page_size = 1000
    offset = 0
    total = 0
    conn = get_connection()

    while True:
        response = (
            client.table("wb_tariffs")
            .select("dt, warehouse_name, delivery_coef, logistics_1l, "
                    "logistics_extra_l, storage_1l_day, storage_coef, geo_name")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            break
        # Map Supabase column `storage_1l_day` → SQLite column `box_storage_base`.
        mapped = [
            {
                "dt": r["dt"],
                "warehouse_name": r["warehouse_name"],
                "delivery_coef": r["delivery_coef"],
                "logistics_1l": r["logistics_1l"],
                "logistics_extra_l": r["logistics_extra_l"],
                "box_storage_base": r["storage_1l_day"],
                "storage_coef": r["storage_coef"],
                "geo_name": r.get("geo_name") or "",
            }
            for r in rows
        ]
        conn.executemany(_INSERT_SQL, mapped)
        conn.commit()
        total += len(rows)
        logger.info("Migrated %d rows (running total: %d)", len(rows), total)
        if len(rows) < page_size:
            break
        offset += page_size

    print(f"Done: {total} wb_tariffs rows migrated to SQLite")
    return 0


if __name__ == "__main__":
    sys.exit(main())
