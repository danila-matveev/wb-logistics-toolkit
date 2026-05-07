from __future__ import annotations
from collections import defaultdict

from localization.data.mappings import get_warehouse_fd, get_delivery_fd


def calculate_sku_localization(orders: list[dict]) -> dict[int, float]:
    """Calculate per-SKU localization % from WB orders.

    An order is "local" if the warehouse's federal district matches
    the delivery oblast's federal district.
    """
    sku_local: dict[int, int] = defaultdict(int)
    sku_total: dict[int, int] = defaultdict(int)

    for order in orders:
        nm_id = order.get("nmId", 0)
        if not nm_id:
            continue

        wh_name = order.get("warehouseName", "")
        oblast = order.get("oblastOkrugName", "") or order.get("oblast", "")

        wh_fd = get_warehouse_fd(wh_name)
        delivery_fd = get_delivery_fd(oblast)

        if not wh_fd or not delivery_fd:
            continue

        sku_total[nm_id] += 1
        if wh_fd == delivery_fd:
            sku_local[nm_id] += 1

    result: dict[int, float] = {}
    for nm_id, total in sku_total.items():
        if total > 0:
            result[nm_id] = round(sku_local[nm_id] / total * 100, 2)
    return result
