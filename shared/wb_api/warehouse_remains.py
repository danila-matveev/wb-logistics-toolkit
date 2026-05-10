from __future__ import annotations

import logging
import time
from typing import Any

from .client import WBClient

logger = logging.getLogger(__name__)


def fetch_warehouse_remains(
    client: WBClient,
    *,
    poll_interval: float = 5.0,
    timeout: float = 600.0,
) -> list[dict[str, Any]]:
    """Fetch current stock remains per warehouse per nm_id.

    Uses the WB seller-analytics-api async report flow:
      1. GET /api/v1/warehouse_remains?... → returns taskId
      2. Poll /tasks/{taskId}/status until status == "done"
      3. GET /tasks/{taskId}/download → hierarchical list

    The download response groups warehouses[] under each nmId. We flatten it
    to the legacy shape used by callers: a list of dicts with at minimum
    {vendorCode, nmId, warehouseName, quantity, volume, techSize}.
    """
    params = {
        "locale": "ru",
        "groupByBrand": "false",
        "groupBySubject": "false",
        "groupBySa": "true",
        "groupByNm": "true",
        "groupByBarcode": "false",
        "groupBySize": "true",
        "filterPics": "0",
        "filterVolume": "0",
    }
    create = client.get(
        base=WBClient.ANALYTICS_URL,
        path="/api/v1/warehouse_remains",
        params=params,
    )
    task_id = (create or {}).get("data", {}).get("taskId")
    if not task_id:
        raise RuntimeError(f"WB warehouse_remains: no taskId in response: {create!r}")

    deadline = time.time() + timeout
    status: str | None = None
    while time.time() < deadline:
        time.sleep(poll_interval)
        status_resp = client.get(
            base=WBClient.ANALYTICS_URL,
            path=f"/api/v1/warehouse_remains/tasks/{task_id}/status",
        )
        status = (status_resp or {}).get("data", {}).get("status")
        logger.info("warehouse_remains task %s status=%s", task_id, status)
        if status == "done":
            break
        if status in ("canceled", "purged"):
            raise RuntimeError(
                f"WB warehouse_remains task {task_id} failed: status={status}"
            )
    else:
        raise RuntimeError(
            f"WB warehouse_remains task {task_id} timeout after {timeout}s "
            f"(last status={status})"
        )

    download = client.get(
        base=WBClient.ANALYTICS_URL,
        path=f"/api/v1/warehouse_remains/tasks/{task_id}/download",
    )
    if not isinstance(download, list):
        return []

    flat: list[dict[str, Any]] = []
    for item in download:
        base = {
            "vendorCode": item.get("vendorCode") or "",
            "nmId": item.get("nmId") or 0,
            "barcode": item.get("barcode") or "",
            "techSize": item.get("techSize") or "",
            "volume": float(item.get("volume") or 0),
            "brand": item.get("brand") or "",
            "subjectName": item.get("subjectName") or "",
        }
        warehouses = item.get("warehouses") or []
        if not warehouses:
            flat.append({**base, "warehouseName": "", "quantity": 0})
            continue
        for wh in warehouses:
            flat.append(
                {
                    **base,
                    "warehouseName": wh.get("warehouseName") or "",
                    "quantity": int(wh.get("quantity") or 0),
                }
            )
    return flat
