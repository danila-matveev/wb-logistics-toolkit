from __future__ import annotations

from datetime import date as _date
from typing import Any

from .client import WBClient


def fetch_box_tariffs(
    client: WBClient,
    date: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch current box delivery tariffs per warehouse.

    Args:
        client: WBClient instance.
        date: ISO date (YYYY-MM-DD). Defaults to today if None.

    Returns:
        List of warehouse tariff dicts with warehouseName, boxDeliveryBase, etc.
    """
    params: dict[str, Any] = {"date": date or _date.today().isoformat()}
    data = client.get(
        base=WBClient.COMMON_URL,
        path="/api/v1/tariffs/box",
        params=params,
    )
    return data.get("response", {}).get("data", {}).get("warehouseList", [])


def fetch_pallet_tariffs(
    client: WBClient,
    date: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch pallet delivery tariffs per warehouse.

    Args:
        client: WBClient instance.
        date: ISO date (YYYY-MM-DD). Defaults to today if None.

    Returns:
        List of warehouse tariff dicts with warehouseName and pallet pricing.
    """
    params: dict[str, Any] = {"date": date or _date.today().isoformat()}
    data = client.get(
        base=WBClient.COMMON_URL,
        path="/api/v1/tariffs/pallet",
        params=params,
    )
    return data.get("response", {}).get("data", {}).get("warehouseList", [])
