# tests/shared/wb_api/test_endpoints.py
from unittest.mock import MagicMock, patch

from shared.wb_api.client import WBClient
from shared.wb_api.orders import fetch_orders
from shared.wb_api.tariffs import fetch_box_tariffs
from shared.wb_api.warehouse_remains import fetch_warehouse_remains
from shared.wb_api.content import fetch_nm_volumes
from shared.wb_api.reports import fetch_report


def make_client():
    return WBClient(token="test_token")


def test_fetch_orders_calls_correct_endpoint():
    client = make_client()
    mock_data = [{"supplierArticle": "art1", "warehouseName": "Коледино"}]

    with patch.object(client, "get", return_value=mock_data) as mock_get:
        result = fetch_orders(client, date_from="2026-01-01")

    mock_get.assert_called_once()
    call_args = mock_get.call_args
    assert "/api/v1/supplier/orders" in call_args[1].get("path", call_args[0][1])
    assert result == mock_data


def test_fetch_orders_excludes_cancelled_by_default():
    client = make_client()
    raw = [
        {"supplierArticle": "a", "isCancel": False},
        {"supplierArticle": "b", "isCancel": True},
    ]
    with patch.object(client, "get", return_value=raw):
        result = fetch_orders(client, date_from="2026-01-01", exclude_cancelled=True)
    assert len(result) == 1
    assert result[0]["supplierArticle"] == "a"


def test_fetch_box_tariffs_returns_list():
    client = make_client()
    mock_resp = {"response": {"data": {"warehouseList": [
        {"warehouseName": "Коледино", "boxDeliveryBase": 46.0}
    ]}}}
    with patch.object(client, "get", return_value=mock_resp):
        result = fetch_box_tariffs(client)
    assert isinstance(result, list)
    assert result[0]["warehouseName"] == "Коледино"


def test_fetch_warehouse_remains_returns_list():
    client = make_client()
    mock_resp = [{"warehouseName": "Коледино", "nmId": 123, "quantity": 50}]
    with patch.object(client, "get", return_value=mock_resp):
        result = fetch_warehouse_remains(client)
    assert result == mock_resp


def test_fetch_nm_volumes_returns_dict():
    client = make_client()
    mock_resp = {"data": {"cards": [
        {"nmID": 123, "dimensions": {"length": 10, "width": 10, "height": 10}}
    ]}}
    with patch.object(client, "post", return_value=mock_resp):
        result = fetch_nm_volumes(client, nm_ids=[123])
    assert isinstance(result, dict)
    assert 123 in result


def test_fetch_report_returns_list():
    client = make_client()
    mock_data = [{"realizationreport_id": 1, "quantity": 5}]
    with patch.object(client, "get", return_value=mock_data):
        result = fetch_report(client, date_from="2026-01-01", date_to="2026-03-31")
    assert result == mock_data


def test_fetch_report_pagination_stops_on_short_page():
    client = make_client()
    page1 = [{"rrd_id": i, "quantity": 1} for i in range(100_000)]
    page2 = [{"rrd_id": 100_000, "quantity": 1}]

    call_count = 0

    def mock_get(**kwargs):
        nonlocal call_count
        call_count += 1
        return page1 if call_count == 1 else page2

    with patch.object(client, "get", side_effect=mock_get):
        result = fetch_report(client, date_from="2026-01-01", date_to="2026-03-31", limit=100_000)

    assert len(result) == 100_001
    assert call_count == 2
