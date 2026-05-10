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


def test_fetch_warehouse_remains_async_flow_returns_flat_list():
    client = make_client()
    create_resp = {"data": {"taskId": "task-xyz"}}
    status_resp = {"data": {"status": "done"}}
    download_resp = [
        {
            "vendorCode": "art1",
            "nmId": 123,
            "barcode": "bc1",
            "techSize": "M",
            "volume": 1.5,
            "brand": "B",
            "subjectName": "S",
            "warehouses": [
                {"warehouseName": "Коледино", "quantity": 50},
                {"warehouseName": "Электросталь", "quantity": 30},
            ],
        }
    ]
    with patch.object(
        client,
        "get",
        side_effect=[create_resp, status_resp, download_resp],
    ):
        result = fetch_warehouse_remains(client, poll_interval=0)
    assert len(result) == 2
    assert {row["warehouseName"] for row in result} == {"Коледино", "Электросталь"}
    assert all(row["nmId"] == 123 for row in result)
    assert all(row["volume"] == 1.5 for row in result)
    assert sum(row["quantity"] for row in result) == 80


def test_fetch_nm_volumes_filters_to_requested_nm_ids():
    client = make_client()
    page1 = {
        "cards": [
            {"nmID": 123, "dimensions": {"length": 10, "width": 10, "height": 10}},
            {"nmID": 999, "dimensions": {"length": 5, "width": 5, "height": 5}},
        ],
        "cursor": {"updatedAt": "2026-04-01T00:00:00Z", "nmID": 999, "total": 2},
    }
    with patch.object(client, "post", return_value=page1):
        result = fetch_nm_volumes(client, nm_ids=[123])
    assert result == {123: 1.0}


def test_fetch_nm_volumes_paginates_until_short_page():
    client = make_client()
    page1_cards = [
        {"nmID": i, "dimensions": {"length": 10, "width": 10, "height": 10}}
        for i in range(1, 101)
    ]
    page1 = {"cards": page1_cards, "cursor": {"updatedAt": "T1", "nmID": 100, "total": 100}}
    page2 = {"cards": [
        {"nmID": 200, "dimensions": {"length": 10, "width": 10, "height": 10}},
    ], "cursor": {"updatedAt": "T2", "nmID": 200, "total": 1}}
    with patch.object(client, "post", side_effect=[page1, page2]):
        result = fetch_nm_volumes(client, nm_ids=[50, 200, 9999])
    assert result == {50: 1.0, 200: 1.0}


def test_fetch_nm_volumes_empty_input_returns_empty():
    client = make_client()
    with patch.object(client, "post") as p:
        result = fetch_nm_volumes(client, nm_ids=[])
    assert result == {}
    p.assert_not_called()


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
