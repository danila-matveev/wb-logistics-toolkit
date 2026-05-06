# tests/shared/test_config.py
import os
import pytest
import yaml
from pathlib import Path

from shared.config import load_cabinets, get_cabinet, Cabinet


SAMPLE_YAML = """
cabinets:
  - name: test_shop
    sheet_id: "1AbCde"
  - name: other
    sheet_id: "2XyZab"
"""


@pytest.fixture
def cabinets_file(tmp_path):
    f = tmp_path / "cabinets.yaml"
    f.write_text(SAMPLE_YAML)
    return f


def test_load_cabinets_returns_cabinet_dataclasses(cabinets_file, monkeypatch):
    monkeypatch.setenv("WB_TOKEN_TEST_SHOP", "token_aaa")
    monkeypatch.setenv("WB_TOKEN_OTHER", "token_bbb")
    cabinets = load_cabinets(cabinets_file)
    assert len(cabinets) == 2
    assert isinstance(cabinets[0], Cabinet)


def test_load_cabinets_maps_token_from_env(cabinets_file, monkeypatch):
    monkeypatch.setenv("WB_TOKEN_TEST_SHOP", "token_aaa")
    monkeypatch.setenv("WB_TOKEN_OTHER", "token_bbb")
    cabinets = load_cabinets(cabinets_file)
    assert cabinets[0].wb_token == "token_aaa"
    assert cabinets[0].sheet_id == "1AbCde"
    assert cabinets[0].name == "test_shop"


def test_load_cabinets_raises_if_token_missing(cabinets_file, monkeypatch):
    monkeypatch.delenv("WB_TOKEN_TEST_SHOP", raising=False)
    monkeypatch.delenv("WB_TOKEN_OTHER", raising=False)
    with pytest.raises(ValueError, match="WB_TOKEN_TEST_SHOP"):
        load_cabinets(cabinets_file)


def test_get_cabinet_returns_correct_cabinet(cabinets_file, monkeypatch):
    monkeypatch.setenv("WB_TOKEN_TEST_SHOP", "token_aaa")
    monkeypatch.setenv("WB_TOKEN_OTHER", "token_bbb")
    cab = get_cabinet("other", cabinets_file)
    assert cab.name == "other"
    assert cab.wb_token == "token_bbb"


def test_get_cabinet_raises_for_unknown_name(cabinets_file, monkeypatch):
    monkeypatch.setenv("WB_TOKEN_TEST_SHOP", "token_aaa")
    monkeypatch.setenv("WB_TOKEN_OTHER", "token_bbb")
    with pytest.raises(ValueError, match="not found"):
        get_cabinet("nonexistent", cabinets_file)


def test_load_warehouse_statuses(tmp_path):
    from shared.config import load_warehouse_statuses, WarehouseStatus
    wh_file = tmp_path / "warehouse_status.yaml"
    wh_file.write_text("""
warehouses:
  - name: Коледино
    fd: Центральный
    available: true
    redistribution_limit_per_day: 100000
  - name: Новосибирск
    fd: Дальневосточный + Сибирский
    available: false
    reason: Закрыт
    redistribution_limit_per_day: 5000
""")
    statuses = load_warehouse_statuses(wh_file)
    assert len(statuses) == 2
    koledino = statuses["Коледино"]
    assert koledino.available is True
    assert koledino.redistribution_limit_per_day == 100000
    nsk = statuses["Новосибирск"]
    assert nsk.available is False


def test_load_warehouse_statuses_available_only(tmp_path):
    from shared.config import load_warehouse_statuses
    wh_file = tmp_path / "warehouse_status.yaml"
    wh_file.write_text("""
warehouses:
  - name: Коледино
    fd: Центральный
    available: true
    redistribution_limit_per_day: 100000
  - name: Новосибирск
    fd: Дальневосточный + Сибирский
    available: false
    redistribution_limit_per_day: 5000
""")
    statuses = load_warehouse_statuses(wh_file, available_only=True)
    assert "Коледино" in statuses
    assert "Новосибирск" not in statuses
