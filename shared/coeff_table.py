# shared/coeff_table.py
"""KTR/KRP coefficient table — embedded constant, source: WB Partners → Тарифы.

Effective from 2026-03-27. Update by editing COEFF_TABLE below + bumping the
"effective from" comment. No external storage; the table changes ~once a year.
"""
from __future__ import annotations

import warnings
from typing import Any

# KTR/KRP table effective from 27.03.2026 (source: WB Partners → Тарифы).
COEFF_TABLE: list[dict[str, Any]] = [
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


def get_ktr_krp(localization_pct: float) -> tuple[float, float]:
    """Return (КТР, КРП%) for a given per-article localization percentage."""
    loc = max(0.0, min(100.0, localization_pct))
    for row in COEFF_TABLE:
        if row["min_loc"] <= loc <= row["max_loc"]:
            return float(row["ktr"]), float(row["krp_pct"])
    warnings.warn(
        f"No coefficient row found for localization_pct={localization_pct:.2f} "
        f"(clamped={loc:.2f}). Using fallback (2.20, 2.50).",
        RuntimeWarning,
        stacklevel=2,
    )
    return 2.20, 2.50


def get_coeff_table() -> list[dict[str, Any]]:
    """Return the full coefficient table (read-only reference)."""
    return COEFF_TABLE


def calc_financial_impact(
    krp_pct: float,
    price: float,
    orders: int,
    period_days: int,
) -> float:
    """Monthly ИРП financial impact in ₽."""
    if krp_pct <= 0 or price <= 0 or orders <= 0 or period_days <= 0:
        return 0.0
    daily_orders = orders / period_days
    monthly_orders = daily_orders * 30
    return krp_pct / 100.0 * price * monthly_orders
