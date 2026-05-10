from __future__ import annotations

from typing import Any

import httpx


class WBClient:
    """Token-agnostic WB API HTTP client.

    Usage:
        client = WBClient(token="eyJ...")
        data = client.get(base=WBClient.STATS_URL, path="/api/v1/supplier/orders",
                          params={"dateFrom": "2026-01-01"})
    """

    STATS_URL = "https://statistics-api.wildberries.ru"
    CONTENT_URL = "https://content-api.wildberries.ru"
    SUPPLY_URL = "https://supplies-api.wildberries.ru"
    ANALYTICS_URL = "https://seller-analytics-api.wildberries.ru"
    COMMON_URL = "https://common-api.wildberries.ru"

    def __init__(self, token: str, timeout: float = 120.0) -> None:
        self.token = token
        self.timeout = timeout
        self._headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

    def get(
        self,
        base: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """GET request, returns parsed JSON. Raises httpx.HTTPStatusError on 4xx/5xx."""
        url = f"{base}{path}"
        with httpx.Client(timeout=self.timeout) as http:
            response = http.get(url, headers=self._headers, params=params or {})
            response.raise_for_status()
            return response.json()

    def post(
        self,
        base: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """POST request, returns parsed JSON. Raises httpx.HTTPStatusError on 4xx/5xx."""
        url = f"{base}{path}"
        with httpx.Client(timeout=self.timeout) as http:
            response = http.post(url, headers=self._headers, json=json or {})
            response.raise_for_status()
            return response.json()
