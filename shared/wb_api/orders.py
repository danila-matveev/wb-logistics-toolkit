from __future__ import annotations

from typing import Any

from .client import WBClient


def fetch_orders(
    client: WBClient,
    date_from: str,
    flag: int = 0,
    exclude_cancelled: bool = False,
) -> list[dict[str, Any]]:
    """Fetch supplier orders from WB Statistics API.

    Args:
        client: WBClient instance.
        date_from: ISO date string, e.g. "2026-01-01".
        flag: 0 = all orders since date_from, 1 = only updated orders.
        exclude_cancelled: If True, filter out isCancel=True rows.

    Returns:
        List of order dicts from WB API.
    """
    data = client.get(
        WBClient.STATS_URL,
        "/api/v1/supplier/orders",
        params={"dateFrom": date_from, "flag": flag},
    )
    orders: list[dict[str, Any]] = data if isinstance(data, list) else []
    if exclude_cancelled:
        orders = [o for o in orders if not o.get("isCancel", False)]
    return orders
