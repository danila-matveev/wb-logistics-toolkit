from __future__ import annotations

from typing import Any

from .client import WBClient


def fetch_nm_volumes(
    client: WBClient,
    nm_ids: list[int],
    batch_size: int = 100,
) -> dict[int, float]:
    """Fetch product dimensions from WB Content API and compute volume in litres.

    Args:
        client: WBClient instance.
        nm_ids: List of WB nm_id (article IDs).
        batch_size: Max IDs per API request (WB limit is 100).

    Returns:
        Dict mapping nm_id → volume in litres (length×width×height / 1000).
    """
    result: dict[int, float] = {}

    for i in range(0, len(nm_ids), batch_size):
        batch = nm_ids[i : i + batch_size]
        resp = client.post(
            base=WBClient.CONTENT_URL,
            path="/content/v2/get/cards/list",
            json={"settings": {"cursor": {"nmIDs": batch, "limit": batch_size}}},
        )
        cards = resp.get("data", {}).get("cards", [])
        for card in cards:
            nm_id = card.get("nmID")
            dims = card.get("dimensions", {})
            length = dims.get("length", 0) or 0
            width = dims.get("width", 0) or 0
            height = dims.get("height", 0) or 0
            if nm_id and length and width and height:
                result[nm_id] = round(length * width * height / 1000, 3)

    return result
