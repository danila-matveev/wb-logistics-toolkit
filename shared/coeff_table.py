from __future__ import annotations

from datetime import date
from typing import Any

from .supabase import get_supabase_client

_cache: list[dict[str, Any]] | None = None


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
    return 2.20, 2.50


def clear_cache() -> None:
    """Clear the in-memory coefficient table cache (used in tests)."""
    global _cache
    _cache = None
