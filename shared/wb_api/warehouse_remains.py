from __future__ import annotations

from typing import Any

from .client import WBClient


def fetch_warehouse_remains(client: WBClient) -> list[dict[str, Any]]:
    """Fetch current stock remains per warehouse per nm_id.

    Returns:
        List of dicts with warehouseName, nmId, quantity, etc.
    """
    data = client.get(
        base=WBClient.STATS_URL,
        path="/api/v1/warehouse/remains",
    )
    return data if isinstance(data, list) else []
