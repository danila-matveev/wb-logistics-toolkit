"""API-driven stock permutation recommender.

Replaces generate_localization_report_v3.py (Excel-based) with a version
that reads live WB API data: warehouse_remains for stocks,
Phase 1 cache (il_irp["articles"][*]["regions"]) for order distribution.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from shared.config import WarehouseStatus
from localization.data.mappings import (
    CIS_REGIONS,
    PREFERRED_WAREHOUSES,
    RU_FEDERAL_DISTRICTS,
    SKIP_WAREHOUSES,
    get_warehouse_fd,
)

TARGET_LOC_PCT: float = 80.0
DEFAULT_SAFETY_DAYS: int = 14
DEFAULT_MIN_DONOR_LOC: float = 70.0


def _aggregate_stocks_by_fd(
    warehouse_remains: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Aggregate warehouse_remains into {article_lower → {fd → stock_qty}}.

    Skips SKIP_WAREHOUSES (transit) and CIS warehouses.
    """
    result: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for item in warehouse_remains:
        article = (item.get("vendorCode") or "").lower()
        wh = item.get("warehouseName") or ""
        qty = int(item.get("quantity") or 0)
        if not article or qty <= 0 or wh in SKIP_WAREHOUSES:
            continue
        fd = get_warehouse_fd(wh)
        if fd is None or fd in CIS_REGIONS:
            continue
        result[article][fd] += qty
    return dict(result)


def _donor_available(
    fd_stock: int,
    fd_orders_total: int,
    period_days: int,
    safety_days: int,
) -> int:
    """Units available from a donor FD after reserving safety buffer.

    Args:
        fd_stock: Current stock in this FD.
        fd_orders_total: Total orders (local+nonlocal) in this FD over period_days.
        period_days: Period length in days.
        safety_days: Days of demand to reserve as safety buffer.

    Returns:
        Units that can be transferred without going below safety buffer.
    """
    if fd_orders_total == 0:
        return fd_stock
    daily_orders = fd_orders_total / period_days
    safe_min = math.ceil(daily_orders * safety_days)
    return max(0, fd_stock - safe_min)


def generate_movements(
    articles: list[dict[str, Any]],
    warehouse_remains: list[dict[str, Any]],
    warehouse_statuses: dict[str, WarehouseStatus],
    period_days: int = 30,
    safety_days: int = DEFAULT_SAFETY_DAYS,
    min_donor_loc_pct: float = DEFAULT_MIN_DONOR_LOC,
    target_loc_pct: float = TARGET_LOC_PCT,
) -> dict[str, Any]:
    """Generate movement and supply recommendations for sub-target articles.

    Args:
        articles: Output of analyze_il_irp()["articles"].
        warehouse_remains: Output of fetch_warehouse_remains().
        warehouse_statuses: Output of load_warehouse_statuses().
        period_days: Period length for safety buffer calculation.
        safety_days: Days of stock to reserve for donor protection.
        min_donor_loc_pct: Not used directly (safety_days is primary guard).
        target_loc_pct: Articles at or above this % are skipped.

    Returns:
        {
            "movements": [{article, from_fd, from_warehouse, to_fd, to_warehouse,
                           qty, impact_rub}],
            "supplies":  [{article, to_fd, to_warehouse, qty}],
            "region_summary": [{fd, stock_total, orders_total, loc_pct}],
        }
    """
    fd_stocks = _aggregate_stocks_by_fd(warehouse_remains)

    movements: list[dict[str, Any]] = []
    supplies: list[dict[str, Any]] = []

    # Sort by impact: (ktr-1) × total_orders descending
    problem_articles = [
        a for a in articles
        if a.get("loc_pct", 100.0) < target_loc_pct and a.get("wb_total", 0) > 0
    ]
    problem_articles.sort(
        key=lambda a: (a.get("ktr", 1.0) - 1.0) * a.get("wb_total", 0),
        reverse=True,
    )

    for article in problem_articles:
        art_lower = article["article"].lower()
        regions: dict[str, dict[str, Any]] = article.get("regions", {})
        total_orders = article.get("wb_total", 0)

        if total_orders == 0:
            continue

        art_fd_stocks = dict(fd_stocks.get(art_lower, {}))
        total_stock = sum(art_fd_stocks.values())

        # Build donor/recipient maps for RU FDs only
        donor_available: dict[str, int] = {}
        recipient_deficit: dict[str, int] = {}

        for fd in RU_FEDERAL_DISTRICTS:
            region_data = regions.get(fd, {})
            fd_order_total = region_data.get("total", 0)
            fd_stock = art_fd_stocks.get(fd, 0)

            demand_share = fd_order_total / total_orders if total_orders > 0 else 0
            target_stock = demand_share * total_stock

            if fd_stock > target_stock and fd_stock > 0:
                avail = _donor_available(fd_stock, fd_order_total, period_days, safety_days)
                cap = int(min(avail, fd_stock - round(target_stock)))
                if cap > 0:
                    donor_available[fd] = cap
            elif round(target_stock) > fd_stock:
                deficit = round(target_stock) - fd_stock
                if deficit > 0:
                    recipient_deficit[fd] = deficit

        # Greedy matching: donors → recipients
        remaining_donors = dict(donor_available)
        for recipient_fd, needed in sorted(
            recipient_deficit.items(), key=lambda x: x[1], reverse=True
        ):
            transferred = 0
            for donor_fd, avail in list(remaining_donors.items()):
                if avail <= 0 or needed - transferred <= 0:
                    continue
                transfer = min(avail, needed - transferred)

                from_wh = PREFERRED_WAREHOUSES.get(donor_fd, donor_fd)
                to_wh = PREFERRED_WAREHOUSES.get(recipient_fd, recipient_fd)

                # Prefer available warehouse from statuses
                if to_wh in warehouse_statuses and not warehouse_statuses[to_wh].available:
                    alt = next(
                        (ws.name for ws in warehouse_statuses.values()
                         if ws.fd == recipient_fd and ws.available),
                        to_wh,
                    )
                    to_wh = alt

                movements.append({
                    "article": article["article"],
                    "from_fd": donor_fd,
                    "from_warehouse": from_wh,
                    "to_fd": recipient_fd,
                    "to_warehouse": to_wh,
                    "qty": transfer,
                    "impact_rub": 0.0,
                })

                remaining_donors[donor_fd] -= transfer
                transferred += transfer

            unfilled = needed - transferred
            if unfilled > 0:
                to_wh = PREFERRED_WAREHOUSES.get(recipient_fd, recipient_fd)
                supplies.append({
                    "article": article["article"],
                    "to_fd": recipient_fd,
                    "to_warehouse": to_wh,
                    "qty": unfilled,
                })

    # Region summary: aggregate across all articles
    fd_agg: dict[str, dict[str, float]] = defaultdict(lambda: {"stock": 0, "orders": 0, "local": 0})
    for article in articles:
        art_lower = article["article"].lower()
        art_stocks = fd_stocks.get(art_lower, {})
        for fd in RU_FEDERAL_DISTRICTS:
            region_data = article.get("regions", {}).get(fd, {})
            fd_agg[fd]["stock"] += art_stocks.get(fd, 0)
            fd_agg[fd]["orders"] += region_data.get("total", 0)
            fd_agg[fd]["local"] += region_data.get("local", 0)

    region_summary = [
        {
            "fd": fd,
            "stock_total": int(data["stock"]),
            "orders_total": int(data["orders"]),
            "loc_pct": round(data["local"] / data["orders"] * 100, 1)
            if data["orders"] > 0 else 0.0,
        }
        for fd, data in sorted(fd_agg.items())
    ]

    return {
        "movements": movements,
        "supplies": supplies,
        "region_summary": region_summary,
    }
