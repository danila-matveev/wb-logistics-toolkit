from datetime import date
from unittest.mock import patch, MagicMock
from audit.etl.tariff_collector import build_upsert_rows


def test_build_upsert_rows_from_api_list():
    raw_tariffs = [
        {
            "warehouseName": "Коледино",
            "boxDeliveryBase": "46,0",
            "boxDeliveryLiter": "14,0",
            "boxDeliveryCoefExpr": "95",
            "boxStorageBase": "0",
            "boxStorageLiter": "0",
            "boxStorageCoefExpr": "0",
        }
    ]
    rows = build_upsert_rows(date(2026, 5, 1), raw_tariffs)
    assert len(rows) == 1
    assert rows[0]["warehouse_name"] == "Коледино"
    assert rows[0]["delivery_coef"] == 95
    assert rows[0]["logistics_1l"] == 46.0
    assert rows[0]["dt"] == "2026-05-01"


def test_build_upsert_rows_empty():
    assert build_upsert_rows(date(2026, 5, 1), []) == []


def test_collect_tariffs_inserts_into_sqlite(tmp_path, monkeypatch):
    """Smoke: collect_tariffs() upserts rows into SQLite via INSERT ... ON CONFLICT."""
    db_path = tmp_path / "etl.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    from shared import db as db_module
    db_module._reset_for_tests()

    fake_raw = [
        {
            "warehouseName": "Коледино",
            "boxDeliveryBase": "46,0",
            "boxDeliveryLiter": "14,0",
            "boxDeliveryCoefExpr": "95",
            "boxStorageBase": "0",
            "boxStorageLiter": "0",
            "boxStorageCoefExpr": "0",
        }
    ]
    fake_cab = MagicMock()
    fake_cab.wb_token = "tok"

    with patch("audit.etl.tariff_collector.get_cabinet", return_value=fake_cab), \
         patch("audit.etl.tariff_collector.WBClient"), \
         patch("audit.etl.tariff_collector.fetch_box_tariffs", return_value=fake_raw):
        from audit.etl.tariff_collector import collect_tariffs
        count = collect_tariffs(date(2026, 5, 1), "ooo")

    assert count == 1
    conn = db_module.get_connection()
    rows = conn.execute("SELECT * FROM wb_tariffs").fetchall()
    assert len(rows) == 1
    assert rows[0]["warehouse_name"] == "Коледино"
    assert rows[0]["delivery_coef"] == 95.0
    assert rows[0]["dt"] == "2026-05-01"

    # Run again — should UPSERT, not duplicate
    with patch("audit.etl.tariff_collector.get_cabinet", return_value=fake_cab), \
         patch("audit.etl.tariff_collector.WBClient"), \
         patch("audit.etl.tariff_collector.fetch_box_tariffs", return_value=fake_raw):
        from audit.etl.tariff_collector import collect_tariffs
        collect_tariffs(date(2026, 5, 1), "ooo")
    rows = conn.execute("SELECT * FROM wb_tariffs").fetchall()
    assert len(rows) == 1

    db_module._reset_for_tests()
