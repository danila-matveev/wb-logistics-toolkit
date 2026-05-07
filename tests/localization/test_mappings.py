# tests/localization/test_mappings.py
from localization.data.mappings import (
    CIS_REGIONS,
    FD_FULL_NAMES,
    OBLAST_TO_FD,
    PREFERRED_WAREHOUSES,
    RU_FEDERAL_DISTRICTS,
    SKIP_WAREHOUSES,
    WAREHOUSE_TO_FD,
    get_delivery_fd,
    get_warehouse_fd,
    log_unknown_mappings,
)


def test_warehouse_fd_known():
    assert get_warehouse_fd("Коледино") == "Центральный"
    assert get_warehouse_fd("Казань") == "Приволжский"
    assert get_warehouse_fd("Новосибирск") == "Дальневосточный + Сибирский"


def test_warehouse_fd_skip():
    assert get_warehouse_fd("В пути до получателей") is None
    assert get_warehouse_fd("Маркетплейс") is None


def test_warehouse_fd_unknown():
    assert get_warehouse_fd("НесуществующийСклад") is None


def test_warehouse_fd_cis():
    assert get_warehouse_fd("Минск") == "Беларусь"
    assert get_warehouse_fd("Астана Карагандинское шоссе") == "Казахстан"


def test_delivery_fd_oblast():
    assert get_delivery_fd("Московская") == "Центральный"
    assert get_delivery_fd("Московская область") == "Центральный"
    assert get_delivery_fd("Республика Татарстан") == "Приволжский"
    assert get_delivery_fd("Свердловская") == "Уральский"


def test_delivery_fd_full_name():
    assert get_delivery_fd("Центральный федеральный округ") == "Центральный"
    assert get_delivery_fd("Сибирский федеральный округ") == "Дальневосточный + Сибирский"


def test_delivery_fd_unknown():
    assert get_delivery_fd("НесуществующийРегион") is None


def test_preferred_warehouses_keys():
    for fd in RU_FEDERAL_DISTRICTS:
        assert fd in PREFERRED_WAREHOUSES, f"Missing preferred warehouse for {fd}"


def test_ru_federal_districts_count():
    assert len(RU_FEDERAL_DISTRICTS) == 6


def test_cis_regions():
    assert "Беларусь" in CIS_REGIONS
    assert "Казахстан" in CIS_REGIONS


def test_log_unknown_mappings_returns_sets():
    orders = [
        {"warehouseName": "Коледино", "oblastOkrugName": "Московская"},
        {"warehouseName": "НезнакомыйСклад", "oblastOkrugName": "НезнакомыйРегион"},
    ]
    unknown_wh, unknown_obl = log_unknown_mappings(orders)
    assert "НезнакомыйСклад" in unknown_wh
    assert "НезнакомыйРегион" in unknown_obl
