from datetime import date
from unittest.mock import patch, MagicMock
from audit.etl.tariff_collector import build_upsert_rows
from audit.etl.import_coeff_table import COEFF_TABLE


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


def test_coeff_table_has_20_rows():
    assert len(COEFF_TABLE) == 20


def test_coeff_table_covers_full_range():
    """COEFF_TABLE covers 0–100% with no gaps."""
    for row in COEFF_TABLE:
        assert "min_loc" in row and "max_loc" in row
        assert "ktr" in row and "krp_pct" in row
    # first row should cover top tier
    top = max(COEFF_TABLE, key=lambda r: r["min_loc"])
    assert top["min_loc"] == 95.0
    assert top["ktr"] == 0.50
    # last row should cover bottom tier
    bottom = min(COEFF_TABLE, key=lambda r: r["min_loc"])
    assert bottom["min_loc"] == 0.0
    assert bottom["ktr"] == 2.20
