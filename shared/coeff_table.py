from __future__ import annotations

import threading
import warnings
from datetime import date
from typing import Any

from .supabase import get_supabase_client

_cache: list[dict[str, Any]] | None = None
_cache_lock = threading.Lock()


def _load_from_supabase() -> list[dict[str, Any]]:
    client = get_supabase_client()
    response = (
        client.table("wb_coeff_table")
        .select("min_loc, max_loc, ktr, krp_pct")
        .lte("valid_from", date.today().isoformat())
        .order("valid_from", desc=True)
        .execute()
    )
    return response.data or []


def _get_table() -> list[dict[str, Any]]:
    global _cache
    if _cache is not None:
        return _cache
    with _cache_lock:
        if _cache is not None:
            return _cache
        rows = _load_from_supabase()
        if not rows:
            raise RuntimeError(
                "wb_coeff_table is empty in Supabase. "
                "Run: python audit/etl/import_coeff_table.py"
            )
        _cache = rows
    return _cache


def get_ktr_krp(localization_pct: float) -> tuple[float, float]:
    """Return (КТР, КРП%) for a given per-article localization percentage.

    Args:
        localization_pct: Per-article localization % (0.0 – 100.0).

    Returns:
        (ktr, krp_pct) from the WB coefficient table loaded from Supabase.
    """
    loc = max(0.0, min(100.0, localization_pct))
    for row in _get_table():
        if row["min_loc"] <= loc <= row["max_loc"]:
            return float(row["ktr"]), float(row["krp_pct"])
    warnings.warn(
        f"No coefficient row found for localization_pct={localization_pct:.2f} "
        f"(clamped={loc:.2f}). Using fallback (2.20, 2.50). "
        "Check wb_coeff_table in Supabase for coverage gaps.",
        RuntimeWarning,
        stacklevel=2,
    )
    return 2.20, 2.50


def clear_cache() -> None:
    """Clear the in-memory coefficient table cache (used in tests)."""
    global _cache
    with _cache_lock:
        _cache = None


def get_coeff_table() -> list[dict[str, Any]]:
    """Return the full coefficient table (same cached instance as get_ktr_krp uses)."""
    return _get_table()


def calc_financial_impact(
    krp_pct: float,
    price: float,
    orders: int,
    period_days: int,
) -> float:
    """Monthly ИРП financial impact in ₽.

    Args:
        krp_pct: КРП coefficient in percent (e.g. 2.10).
        price: Retail price ₽ per unit.
        orders: Order count for the observed period.
        period_days: Length of the observed period in days.

    Returns:
        Estimated ИРП loss ₽/month.
    """
    if krp_pct <= 0 or price <= 0 or orders <= 0 or period_days <= 0:
        return 0.0
    daily_orders = orders / period_days
    monthly_orders = daily_orders * 30
    return krp_pct / 100.0 * price * monthly_orders
