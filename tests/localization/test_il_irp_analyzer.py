# tests/localization/test_il_irp_analyzer.py
import pytest
from unittest.mock import patch

MOCK_ROWS = [
    {"min_loc": 95.0, "max_loc": 100.0, "ktr": 0.50, "krp_pct": 0.0},
    {"min_loc": 60.0, "max_loc":  64.99, "ktr": 1.00, "krp_pct": 0.0},
    {"min_loc": 55.0, "max_loc":  59.99, "ktr": 1.05, "krp_pct": 2.00},
    {"min_loc":  0.0, "max_loc":   4.99, "ktr": 2.20, "krp_pct": 2.50},
]

# 3 active orders for "art-a":
#   2× Коледино (ЦФО) → Московская (ЦФО)  — LOCAL
#   1× Коледино (ЦФО) → Республика Татарстан (ПФО) — NONLOCAL
# 1 cancelled — ignored
ORDERS = [
    {"supplierArticle": "ART-A", "warehouseName": "Коледино",
     "oblastOkrugName": "Московская", "isCancel": False},
    {"supplierArticle": "ART-A", "warehouseName": "Коледино",
     "oblastOkrugName": "Московская", "isCancel": False},
    {"supplierArticle": "ART-A", "warehouseName": "Коледино",
     "oblastOkrugName": "Республика Татарстан", "isCancel": False},
    {"supplierArticle": "ART-A", "warehouseName": "Коледино",
     "oblastOkrugName": "Московская", "isCancel": True},
]
PRICES = {"art-a": 1000.0}


@pytest.fixture(autouse=True)
def patch_coeff():
    import shared.coeff_table as ct
    ct.clear_cache()
    from unittest.mock import MagicMock
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value \
        .lte.return_value.order.return_value.execute.return_value.data = MOCK_ROWS
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_sb):
        yield
    ct.clear_cache()


def test_structure():
    from localization.calculators.il_irp_analyzer import analyze_il_irp
    result = analyze_il_irp(ORDERS, PRICES)
    assert set(result.keys()) == {"summary", "articles", "top_problems"}


def test_article_counts():
    from localization.calculators.il_irp_analyzer import analyze_il_irp
    result = analyze_il_irp(ORDERS, PRICES)
    arts = {a["article"]: a for a in result["articles"]}
    assert "art-a" in arts
    a = arts["art-a"]
    assert a["wb_local"] == 2
    assert a["wb_nonlocal"] == 1
    assert a["wb_total"] == 3
    assert a["loc_pct"] == pytest.approx(round(2 / 3 * 100, 1))


def test_cancelled_ignored():
    from localization.calculators.il_irp_analyzer import analyze_il_irp
    result = analyze_il_irp(ORDERS, PRICES)
    summary = result["summary"]
    assert summary["total_rf_orders"] == 3


def test_classify_status():
    from localization.calculators.il_irp_analyzer import classify_status
    assert classify_status(0.50) == "Отличная"
    assert classify_status(1.00) == "Нейтральная"
    assert classify_status(1.20) == "Слабая"
    assert classify_status(2.00) == "Критическая"


def test_skip_warehouses_skipped():
    from localization.calculators.il_irp_analyzer import analyze_il_irp
    orders = [
        {"supplierArticle": "ART-B", "warehouseName": "В пути до получателей",
         "oblastOkrugName": "Московская", "isCancel": False},
    ]
    result = analyze_il_irp(orders, {})
    assert len(result["articles"]) == 0


def test_cis_orders_counted_separately():
    from localization.calculators.il_irp_analyzer import analyze_il_irp
    orders = [
        {"supplierArticle": "ART-C", "warehouseName": "Минск",
         "oblastOkrugName": "Беларусь", "isCancel": False},
    ]
    result = analyze_il_irp(orders, {})
    assert result["summary"]["total_cis_orders"] == 1
    assert len(result["articles"]) == 0
