# tests/localization/test_permutation_calculator.py
import pytest
from shared.config import WarehouseStatus
from localization.permutation_calculator import (
    _aggregate_stocks_by_fd,
    generate_movements,
)


def _ws(name: str, fd: str, limit: int = 100_000) -> WarehouseStatus:
    return WarehouseStatus(name=name, fd=fd, available=True,
                           redistribution_limit_per_day=limit)


WAREHOUSE_STATUSES = {
    "Коледино": _ws("Коледино", "Центральный"),
    "Казань": _ws("Казань", "Приволжский"),
    "Краснодар": _ws("Краснодар", "Южный + Северо-Кавказский"),
    "Новосибирск": _ws("Новосибирск", "Дальневосточный + Сибирский"),
}

EMPTY_REGIONS = {
    "Северо-Западный": {"local": 0, "nonlocal": 0, "total": 0, "pct": 0.0},
    "Южный + Северо-Кавказский": {"local": 0, "nonlocal": 0, "total": 0, "pct": 0.0},
    "Приволжский": {"local": 0, "nonlocal": 0, "total": 0, "pct": 0.0},
    "Уральский": {"local": 0, "nonlocal": 0, "total": 0, "pct": 0.0},
    "Дальневосточный + Сибирский": {"local": 0, "nonlocal": 0, "total": 0, "pct": 0.0},
    "Центральный": {"local": 0, "nonlocal": 0, "total": 0, "pct": 0.0},
}


def test_aggregate_stocks_by_fd_basic():
    remains = [
        {"vendorCode": "ART-A", "warehouseName": "Коледино", "quantity": 50},
        {"vendorCode": "ART-A", "warehouseName": "Казань", "quantity": 30},
        {"vendorCode": "art-a", "warehouseName": "Коледино", "quantity": 20},
    ]
    result = _aggregate_stocks_by_fd(remains)
    assert result["art-a"]["Центральный"] == 70  # 50 + 20 (case-normalised)
    assert result["art-a"]["Приволжский"] == 30


def test_aggregate_stocks_skips_transit():
    remains = [
        {"vendorCode": "ART-B", "warehouseName": "В пути до получателей", "quantity": 10},
        {"vendorCode": "ART-B", "warehouseName": "Коледино", "quantity": 5},
    ]
    result = _aggregate_stocks_by_fd(remains)
    assert result["art-b"]["Центральный"] == 5
    assert len(result["art-b"]) == 1


def test_aggregate_stocks_skips_cis():
    remains = [
        {"vendorCode": "ART-C", "warehouseName": "Минск", "quantity": 20},
    ]
    result = _aggregate_stocks_by_fd(remains)
    assert "art-c" not in result


def test_generate_movements_result_structure():
    articles = [{
        "article": "art-a", "loc_pct": 30.0, "ktr": 1.60, "krp_pct": 2.15,
        "wb_total": 10, "price": 1500.0,
        "regions": {
            **EMPTY_REGIONS,  # spread FIRST — explicit keys below override it
            "Центральный": {"local": 8, "nonlocal": 0, "total": 8, "pct": 100.0},
            "Приволжский": {"local": 0, "nonlocal": 2, "total": 2, "pct": 0.0},
        },
    }]
    warehouse_remains = [
        {"vendorCode": "ART-A", "warehouseName": "Коледино", "quantity": 100},
    ]
    result = generate_movements(articles, warehouse_remains, WAREHOUSE_STATUSES)
    assert "movements" in result
    assert "supplies" in result
    assert "region_summary" in result


def test_generate_movements_donor_protection():
    """Donor with 14 days safety buffer must not be fully drained.

    art-a: Центральный has 10 stock, demand=30 orders/30d → daily=1.0
    safe_min = ceil(1.0 * 14) = 14 > stock(10) → available=0 → no movement.
    Приволжский has deficit → goes to supplies.
    """
    articles = [{
        "article": "art-a", "loc_pct": 40.0, "ktr": 1.30, "krp_pct": 2.10,
        "wb_total": 60, "price": 1000.0,
        "regions": {
            **EMPTY_REGIONS,  # spread FIRST
            "Центральный": {"local": 30, "nonlocal": 0, "total": 30, "pct": 100.0},
            "Приволжский": {"local": 0, "nonlocal": 30, "total": 30, "pct": 0.0},
        },
    }]
    warehouse_remains = [
        {"vendorCode": "ART-A", "warehouseName": "Коледино", "quantity": 10},
    ]
    result = generate_movements(articles, warehouse_remains, WAREHOUSE_STATUSES,
                                period_days=30, safety_days=14)
    # No movements possible (donor protected), only supplies
    assert all(m["from_fd"] != "Центральный" or m["qty"] == 0
               for m in result["movements"])


def test_generate_movements_skips_good_articles():
    articles = [{
        "article": "art-ok", "loc_pct": 85.0, "ktr": 0.70, "krp_pct": 0.0,
        "wb_total": 20, "price": 1000.0,
        "regions": {
            **EMPTY_REGIONS,  # spread FIRST
            "Центральный": {"local": 17, "nonlocal": 3, "total": 20, "pct": 85.0},
        },
    }]
    result = generate_movements(articles, [], WAREHOUSE_STATUSES)
    assert len(result["movements"]) == 0
    assert len(result["supplies"]) == 0
