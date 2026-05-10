"""3-tier warehouse coefficient resolution: fixation → SQLite → dlv_prc."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from shared.db import get_connection

logger = logging.getLogger(__name__)


@dataclass
class CoefResult:
    value: float
    source: str   # "fixation" | "sqlite" | "dlv_prc"
    verified: bool  # False only for dlv_prc fallback


def resolve_warehouse_coef(
    dlv_prc: float,
    fixed_coef: float,
    fixation_end: date | None,
    order_date: date | None,
    warehouse_name: str,
    tariffs: dict[str, dict[date, float]],
) -> CoefResult:
    """Resolve warehouse coefficient with 3-tier priority.

    Priority:
    1. Fixed coefficient (if fixation is active: fixation_end > order_date)
    2. Historical tariffs from SQLite
    3. dlv_prc from report (fallback, not verified)
    """
    if fixed_coef > 0 and fixation_end and order_date and fixation_end > order_date:
        return CoefResult(value=fixed_coef, source="fixation", verified=True)

    wh_tariffs = tariffs.get(warehouse_name)
    if wh_tariffs and order_date:
        matching_dates = [d for d in wh_tariffs if d <= order_date]
        if matching_dates:
            closest = max(matching_dates)
            coef = wh_tariffs[closest]
            if coef > 0:
                return CoefResult(value=coef, source="sqlite", verified=True)

    if dlv_prc > 0:
        return CoefResult(value=dlv_prc, source="dlv_prc", verified=False)

    return CoefResult(value=0.0, source="dlv_prc", verified=False)


def load_tariffs(date_from: date, date_to: date) -> dict[str, dict[date, float]]:
    """Load warehouse coefficients from SQLite wb_tariffs table.

    Returns:
        {warehouse_name: {date: delivery_coef / 100}}
    """
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT dt, warehouse_name, delivery_coef "
            "FROM wb_tariffs WHERE dt BETWEEN ? AND ?",
            (date_from.isoformat(), date_to.isoformat()),
        ).fetchall()
    except Exception as e:
        logger.warning("Failed to load tariffs from SQLite: %s", e)
        return {}

    result: dict[str, dict[date, float]] = {}
    for row in rows:
        coef_raw = row["delivery_coef"]
        if coef_raw is None:
            continue
        wh = row["warehouse_name"]
        dt = date.fromisoformat(row["dt"])
        coef = float(coef_raw) / 100.0
        if wh not in result:
            result[wh] = {}
        result[wh][dt] = coef
    logger.info("Loaded SQLite tariffs: %d warehouses", len(result))
    return result
