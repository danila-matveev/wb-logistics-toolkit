from __future__ import annotations

from typing import Any

from .client import WBClient


def fetch_report(
    client: WBClient,
    date_from: str,
    date_to: str,
    rrdid: int = 0,
    limit: int = 100_000,
) -> list[dict[str, Any]]:
    """Fetch reportDetailByPeriod v5 from WB Statistics API.

    Handles pagination: keeps fetching until no more rows returned.

    Args:
        client: WBClient instance.
        date_from: ISO date string "YYYY-MM-DD".
        date_to: ISO date string "YYYY-MM-DD".
        rrdid: Pagination cursor (rrd_id of last fetched row). Start with 0.
        limit: Rows per page (max 100_000).

    Returns:
        Full list of report rows across all pages.
    """
    all_rows: list[dict[str, Any]] = []
    cursor = rrdid

    while True:
        page = client.get(
            base=WBClient.STATS_URL,
            path="/api/v5/supplier/reportDetailByPeriod",
            params={
                "dateFrom": date_from,
                "dateTo": date_to,
                "rrdid": cursor,
                "limit": limit,
            },
        )
        rows: list[dict[str, Any]] = page if isinstance(page, list) else []
        all_rows.extend(rows)
        if len(rows) < limit:
            break
        cursor = rows[-1].get("rrd_id", cursor)
        if cursor == rrdid:
            break

    return all_rows
