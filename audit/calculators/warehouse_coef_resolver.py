"""3-tier warehouse coefficient resolution: fixation → Supabase → dlv_prc."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date

from shared.supabase import get_supabase_client

logger = logging.getLogger(__name__)


@dataclass
class CoefResult:
    value: float
    source: str   # "fixation" | "supabase" | "dlv_prc"
    verified: bool  # False only for dlv_prc fallback


def resolve_warehouse_coef(
    dlv_prc: float,
    fixed_coef: float,
    fixation_end: date | None,
    order_date: date | None,
    warehouse_name: str,
    supabase_tariffs: dict[str, dict[date, float]],
) -> CoefResult:
    """Resolve warehouse coefficient with 3-tier priority.

    Priority:
    1. Fixed coefficient (if fixation is active: fixation_end > order_date)
    2. Supabase wb_tariffs (historical ETL data)
    3. dlv_prc from report (fallback, not verified)
    """
    # Tier 1: Fixed coefficient (fixation active)
    if fixed_coef > 0 and fixation_end and order_date and fixation_end > order_date:
        return CoefResult(value=fixed_coef, source="fixation", verified=True)

    # Tier 2: Supabase historical tariffs
    wh_tariffs = supabase_tariffs.get(warehouse_name)
    if wh_tariffs and order_date:
        matching_dates = [d for d in wh_tariffs if d <= order_date]
        if matching_dates:
            closest = max(matching_dates)
            coef = wh_tariffs[closest]
            if coef > 0:
                return CoefResult(value=coef, source="supabase", verified=True)

    # Tier 3: dlv_prc fallback
    if dlv_prc > 0:
        return CoefResult(value=dlv_prc, source="dlv_prc", verified=False)

    return CoefResult(value=0.0, source="dlv_prc", verified=False)


def load_supabase_tariffs(date_from: date, date_to: date) -> dict[str, dict[date, float]]:
    """Load warehouse coefficients from Supabase wb_tariffs table.

    Returns:
        {warehouse_name: {date: delivery_coef / 100}}
    """
    try:
        client = get_supabase_client()
        rows = (
            client.table("wb_tariffs")
            .select("dt, warehouse_name, delivery_coef")
            .gte("dt", date_from.isoformat())
            .lte("dt", date_to.isoformat())
            .execute()
        ).data or []

        result: dict[str, dict[date, float]] = {}
        for row in rows:
            wh = row["warehouse_name"]
            dt = date.fromisoformat(row["dt"])
            coef = float(row["delivery_coef"]) / 100.0
            if wh not in result:
                result[wh] = {}
            result[wh][dt] = coef
        logger.info("Loaded Supabase tariffs: %d warehouses", len(result))
        return result
    except Exception as e:
        logger.warning("Failed to load Supabase tariffs: %s", e)
        return {}
