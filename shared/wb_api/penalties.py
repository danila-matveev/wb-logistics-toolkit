from __future__ import annotations

from typing import Any

from .client import WBClient


def fetch_measurement_penalties(
    client: WBClient,
    date_to: str,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Fetch measurement penalties (short-delivery fines) from Analytics API."""
    data = client.get(
        base=WBClient.ANALYTICS_URL,
        path="/api/analytics/v1/measurement-penalties",
        params={"dateTo": date_to, "limit": limit},
    )
    return data.get("data", []) if isinstance(data, dict) else []


def fetch_deductions(
    client: WBClient,
    date_to: str,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Fetch deductions (substitutions, incorrect items) from Analytics API."""
    data = client.get(
        base=WBClient.ANALYTICS_URL,
        path="/api/analytics/v1/deductions",
        params={"dateTo": date_to, "limit": limit, "sort": "dtBonus", "order": "desc"},
    )
    return data.get("data", []) if isinstance(data, dict) else []
