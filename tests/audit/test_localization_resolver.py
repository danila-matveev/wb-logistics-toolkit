from audit.calculators.localization_resolver import calculate_sku_localization


def test_local_order():
    orders = [{
        "nmId": 1,
        "warehouseName": "Коледино",
        "oblastOkrugName": "Центральный федеральный округ",
    }]
    result = calculate_sku_localization(orders)
    assert result[1] == 100.0


def test_non_local_order():
    orders = [{
        "nmId": 1,
        "warehouseName": "Коледино",
        "oblastOkrugName": "Приволжский федеральный округ",
    }]
    result = calculate_sku_localization(orders)
    assert result[1] == 0.0


def test_mixed_orders_50pct():
    orders = [
        {"nmId": 1, "warehouseName": "Коледино", "oblastOkrugName": "Центральный федеральный округ"},
        {"nmId": 1, "warehouseName": "Коледино", "oblastOkrugName": "Приволжский федеральный округ"},
    ]
    result = calculate_sku_localization(orders)
    assert result[1] == 50.0


def test_skips_unknown_warehouse():
    orders = [{"nmId": 1, "warehouseName": "НеизвестныйСклад", "oblastOkrugName": "Центральный федеральный округ"}]
    result = calculate_sku_localization(orders)
    assert 1 not in result


def test_skips_empty_nm_id():
    orders = [{"nmId": 0, "warehouseName": "Коледино", "oblastOkrugName": "Центральный федеральный округ"}]
    result = calculate_sku_localization(orders)
    assert not result
