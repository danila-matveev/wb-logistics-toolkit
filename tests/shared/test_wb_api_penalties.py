# tests/shared/test_wb_api_penalties.py
from unittest.mock import MagicMock
from shared.wb_api.penalties import fetch_measurement_penalties, fetch_deductions
from shared.wb_api.client import WBClient


def test_fetch_measurement_penalties_returns_data():
    client = MagicMock(spec=WBClient)
    client.get.return_value = {"data": [{"nmId": 1, "penalty": 10.0}]}
    result = fetch_measurement_penalties(client, "2026-03-25T23:59:59Z")
    assert result == [{"nmId": 1, "penalty": 10.0}]
    client.get.assert_called_once_with(
        base="https://seller-analytics-api.wildberries.ru",
        path="/api/analytics/v1/measurement-penalties",
        params={"dateTo": "2026-03-25T23:59:59Z", "limit": 1000},
    )


def test_fetch_measurement_penalties_empty_response():
    client = MagicMock(spec=WBClient)
    client.get.return_value = {}
    assert fetch_measurement_penalties(client, "2026-03-25T23:59:59Z") == []


def test_fetch_deductions_returns_data():
    client = MagicMock(spec=WBClient)
    client.get.return_value = {"data": [{"id": 42}]}
    result = fetch_deductions(client, "2026-03-25T23:59:59Z")
    assert result == [{"id": 42}]


def test_analytics_url_on_client():
    assert WBClient.ANALYTICS_URL == "https://seller-analytics-api.wildberries.ru"
