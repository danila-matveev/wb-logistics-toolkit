"""Calculate weekly Localization Index (ИЛ) from WB orders."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta

from localization.data.mappings import get_warehouse_fd, get_delivery_fd
from shared.coeff_table import get_ktr_krp


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def calculate_weekly_il(
    orders: list[dict],
    date_from: date,
    date_to: date,
    il_overrides: dict[str, float] | None = None,
) -> tuple[dict[date, float], list[dict]]:
    """Calculate per-week IL for the audit period.

    Returns:
        (week_to_il, il_data)
        - week_to_il: {monday_date: IL_value} for per-row lookup
        - il_data: list of dicts for the ИЛ Excel sheet
    """
    week_local: dict[date, int] = defaultdict(int)
    week_total: dict[date, int] = defaultdict(int)

    for o in orders:
        order_date_str = o.get("date", "")[:10]
        if not order_date_str:
            continue
        try:
            order_date = date.fromisoformat(order_date_str)
        except ValueError:
            continue

        wh_name = o.get("warehouseName", "")
        delivery_region = (
            o.get("oblastOkrugName", "")
            or o.get("oblast", "")
            or o.get("countryName", "")
        )

        wh_fd = get_warehouse_fd(wh_name)
        delivery_fd = get_delivery_fd(delivery_region)

        if not wh_fd or not delivery_fd:
            continue

        mon = _monday(order_date)
        week_total[mon] += 1
        if wh_fd == delivery_fd:
            week_local[mon] += 1

    week_to_il: dict[date, float] = {}

    mon = _monday(date_from)
    end_mon = _monday(date_to)
    all_mondays: list[date] = []
    while mon <= end_mon:
        all_mondays.append(mon)
        mon += timedelta(days=7)

    for mon in all_mondays:
        total = week_total.get(mon, 0)
        local = week_local.get(mon, 0)
        loc_pct = local / total * 100 if total > 0 else 0.0
        il, _ = get_ktr_krp(loc_pct)
        week_to_il[mon] = il

    if il_overrides:
        for date_str, override_il in il_overrides.items():
            try:
                override_date = date.fromisoformat(date_str)
                mon = _monday(override_date)
                if mon in week_to_il:
                    week_to_il[mon] = override_il
            except ValueError:
                pass

    override_mondays: set[date] = set()
    if il_overrides:
        for date_str in il_overrides:
            try:
                override_mondays.add(_monday(date.fromisoformat(date_str)))
            except ValueError:
                pass

    il_data: list[dict] = []
    for mon in sorted(all_mondays, reverse=True):
        sun = mon + timedelta(days=6)
        il_data.append({
            "date": mon.isoformat(),
            "il": week_to_il[mon],
            "date_from": mon.isoformat(),
            "date_to": sun.isoformat(),
            "source": "override" if mon in override_mondays else "calculated",
        })

    return week_to_il, il_data


def get_il_for_date(week_to_il: dict[date, float], order_dt: date | None) -> float | None:
    """Look up the IL value for a specific order date."""
    if order_dt is None or not week_to_il:
        return None
    mon = _monday(order_dt)
    return week_to_il.get(mon)
