import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from audit.run_audit import _parse_args, run_audit
from audit.models.audit_config import AuditConfig


def test_parse_args_basic():
    args = _parse_args(["ooo", "2026-01-01", "2026-03-31"])
    assert args.cabinet == "ooo"
    assert args.date_from == "2026-01-01"
    assert args.date_to == "2026-03-31"
    assert args.ktr == 1.0


def test_parse_args_with_ktr():
    args = _parse_args(["ooo", "2026-01-01", "2026-03-31", "--ktr", "0.8"])
    assert args.ktr == 0.8


def test_run_audit_returns_path():
    config = AuditConfig(
        api_key="tok", date_from=date(2026, 1, 1), date_to=date(2026, 3, 31),
        cabinet="OOO",
    )
    mock_wb = MagicMock()
    with patch("audit.run_audit.WBClient"), \
         patch("audit.run_audit.fetch_report", return_value=[]), \
         patch("audit.run_audit.fetch_box_tariffs", return_value=[]), \
         patch("audit.run_audit.fetch_pallet_tariffs", return_value=[]), \
         patch("audit.run_audit.fetch_card_dimensions", return_value={}), \
         patch("audit.run_audit.fetch_orders", return_value=[]), \
         patch("audit.run_audit.fetch_warehouse_remains", return_value=[]), \
         patch("audit.run_audit.fetch_measurement_penalties", return_value=[]), \
         patch("audit.run_audit.fetch_deductions", return_value=[]), \
         patch("audit.run_audit.load_tariffs", return_value={}), \
         patch("audit.run_audit.calculate_weekly_il", return_value=({}, [])), \
         patch("audit.run_audit.generate_workbook", return_value=mock_wb):
        path = run_audit(config, output_dir="/tmp")
    assert "Аудит логистики" in path
    assert path.endswith(".xlsx")
    mock_wb.save.assert_called_once()
