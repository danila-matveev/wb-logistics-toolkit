# tests/localization/test_il_irp_analyzer.py
import pytest

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
