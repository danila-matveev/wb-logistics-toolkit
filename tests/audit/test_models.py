# tests/audit/test_models.py
from datetime import date
from audit.models.report_row import ReportRow
from audit.models.tariff_snapshot import TariffSnapshot
from audit.models.audit_config import AuditConfig


def test_report_row_from_api_basic():
    d = {
        "nm_id": 123,
        "supplier_oper_name": "Логистика",
        "bonus_type_name": "К клиенту при продаже",
        "delivery_rub": 150.0,
        "dlv_prc": 95.0,
        "office_name": "Коледино",
        "order_dt": "2026-01-15T00:00:00",
    }
    row = ReportRow.from_api(d)
    assert row.nm_id == 123
    assert row.is_logistics is True
    assert row.is_forward_delivery is True
    assert row.is_fixed_rate is False
    assert row.order_dt == date(2026, 1, 15)


def test_report_row_from_api_fixed_rate():
    d = {"bonus_type_name": "От клиента при отмене", "supplier_oper_name": "Логистика"}
    row = ReportRow.from_api(d)
    assert row.is_fixed_rate is True
    assert row.is_forward_delivery is False


def test_report_row_is_logistics_false():
    d = {"supplier_oper_name": "Хранение"}
    row = ReportRow.from_api(d)
    assert row.is_logistics is False


def test_tariff_snapshot_from_api_parses_ru_decimal():
    d = {
        "warehouseName": "Коледино",
        "boxDeliveryBase": "46,0",
        "boxDeliveryLiter": "14,0",
        "boxDeliveryCoefExpr": "95",
        "boxStorageBase": "0",
        "boxStorageLiter": "0",
        "boxStorageCoefExpr": "0",
    }
    snap = TariffSnapshot.from_api(d)
    assert snap.warehouse_name == "Коледино"
    assert snap.box_delivery_base == 46.0
    assert snap.box_delivery_liter == 14.0
    assert snap.delivery_coef_pct == 95


def test_tariff_snapshot_dash_value():
    d = {"warehouseName": "X", "boxDeliveryBase": "-", "boxDeliveryLiter": "0"}
    snap = TariffSnapshot.from_api(d)
    assert snap.box_delivery_base == 0.0


def test_audit_config_defaults():
    cfg = AuditConfig(api_key="tok", date_from=date(2026, 1, 1), date_to=date(2026, 3, 31))
    assert cfg.ktr == 1.0
    assert cfg.cabinet == ""


def test_audit_config_with_cabinet():
    cfg = AuditConfig(
        api_key="tok", date_from=date(2026, 1, 1), date_to=date(2026, 3, 31),
        cabinet="OOO",
    )
    assert cfg.cabinet == "OOO"
