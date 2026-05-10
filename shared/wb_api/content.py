from __future__ import annotations

from typing import Any

from .client import WBClient

PAGE_LIMIT = 100


def _fetch_all_cards(client: WBClient) -> list[dict[str, Any]]:
    """Page through every card in the cabinet via /content/v2/get/cards/list.

    The WB endpoint paginates with `cursor.updatedAt` + `cursor.nmID` from the
    previous page; a page that returns fewer than `limit` cards is the last one.
    Cards live at the top level of the response, not under `data`.
    """
    all_cards: list[dict[str, Any]] = []
    cursor_extra: dict[str, Any] = {}
    while True:
        body = {
            "settings": {
                "cursor": {"limit": PAGE_LIMIT, **cursor_extra},
                "filter": {"withPhoto": -1},
            }
        }
        resp = client.post(
            base=WBClient.CONTENT_URL,
            path="/content/v2/get/cards/list",
            json=body,
        )
        cards = resp.get("cards") or []
        all_cards.extend(cards)
        cursor = resp.get("cursor") or {}
        if len(cards) < PAGE_LIMIT:
            break
        last_updated = cursor.get("updatedAt")
        last_nm = cursor.get("nmID")
        if not last_updated or not last_nm:
            break
        cursor_extra = {"updatedAt": last_updated, "nmID": last_nm}
    return all_cards


def fetch_card_dimensions(
    client: WBClient,
    nm_ids: list[int],
) -> dict[int, dict[str, float]]:
    """Fetch full dimensions {length,width,height,volume} for the given nm_ids.

    The WB endpoint has no nm_id filter — we page through the whole cabinet
    catalogue and filter by `nm_ids` on our side. Volume is in litres.
    """
    wanted = set(nm_ids)
    if not wanted:
        return {}
    result: dict[int, dict[str, float]] = {}
    for card in _fetch_all_cards(client):
        nm_id = card.get("nmID")
        if nm_id not in wanted:
            continue
        dims = card.get("dimensions") or {}
        length = float(dims.get("length") or 0)
        width = float(dims.get("width") or 0)
        height = float(dims.get("height") or 0)
        if length and width and height:
            result[nm_id] = {
                "length": length,
                "width": width,
                "height": height,
                "volume": round(length * width * height / 1000, 3),
            }
    return result


def fetch_nm_volumes(
    client: WBClient,
    nm_ids: list[int],
    batch_size: int = PAGE_LIMIT,
) -> dict[int, float]:
    """Backwards-compatible thin wrapper: returns {nm_id: volume_litres}."""
    return {nm: d["volume"] for nm, d in fetch_card_dimensions(client, nm_ids).items()}
