import openpyxl
from unittest.mock import patch, MagicMock
from datetime import date
from audit.output.excel_generator import generate_workbook, SHEET_NAMES
from audit.models.audit_config import AuditConfig


def test_sheet_names_count():
    assert len(SHEET_NAMES) == 12


def test_recommendations_sheet_present():
    assert "Рекомендации" in SHEET_NAMES


def test_generate_workbook_creates_12_sheets():
    config = AuditConfig(
        api_key="tok", date_from=date(2026, 1, 1), date_to=date(2026, 3, 31),
        cabinet="OOO",
    )
    with patch("audit.output.excel_generator.write_overpayment_formulas"), \
         patch("audit.output.excel_generator.write_overpayment_values"), \
         patch("audit.output.excel_generator.write_svod"), \
         patch("audit.output.excel_generator.write_detail"), \
         patch("audit.output.excel_generator.write_il"), \
         patch("audit.output.excel_generator.write_pivot_by_article"), \
         patch("audit.output.excel_generator.write_logistics_types"), \
         patch("audit.output.excel_generator.write_weekly"), \
         patch("audit.output.excel_generator.write_dimensions"), \
         patch("audit.output.excel_generator.write_tariffs_box"), \
         patch("audit.output.excel_generator.write_tariffs_pallet"), \
         patch("audit.output.excel_generator.write_recommendations"):
        wb = generate_workbook(
            config=config, all_rows=[], logistics_rows=[],
            overpayment_results=[], coefs=[], card_dims={},
            tariffs_box={}, tariffs_pallet={}, wb_volumes={},
        )
    assert len(wb.sheetnames) == 12
    assert "Рекомендации" in wb.sheetnames
