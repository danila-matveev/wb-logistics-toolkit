"""Main Excel generator — creates workbook with all 12 sheets."""
from __future__ import annotations
import openpyxl
from audit.models.audit_config import AuditConfig
from audit.models.report_row import ReportRow
from audit.models.tariff_snapshot import TariffSnapshot
from audit.calculators.logistics_overpayment import OverpaymentResult
from audit.output.sheet_overpayment_formulas import write_overpayment_formulas
from audit.output.sheet_overpayment_values import write_overpayment_values
from audit.output.sheet_svod import write_svod
from audit.output.sheet_detail import write_detail
from audit.output.sheet_il import write_il
from audit.output.sheet_pivot_by_article import write_pivot_by_article
from audit.output.sheet_logistics_types import write_logistics_types
from audit.output.sheet_weekly import write_weekly
from audit.output.sheet_dimensions import write_dimensions
from audit.output.sheet_tariffs_box import write_tariffs_box
from audit.output.sheet_tariffs_pallet import write_tariffs_pallet
from audit.output.sheet_recommendations import write_recommendations

SHEET_NAMES = [
    "Переплата по логистике (короб)",
    "Переплата по логистике",
    "СВОД",
    "Детализация",
    "ИЛ",
    "Переплата по артикулам",
    "Виды логистики",
    "Еженед. отчет",
    "Габариты в карточке",
    "Тарифы короб",
    "Тариф монопалета",
    "Рекомендации",
]


def generate_workbook(
    config: AuditConfig,
    all_rows: list[ReportRow],
    logistics_rows: list[ReportRow],
    overpayment_results: list[OverpaymentResult | None],
    coefs: list[float],
    card_dims: dict[int, dict],
    tariffs_box: dict[str, TariffSnapshot],
    tariffs_pallet: dict,
    wb_volumes: dict[int, float],
    il_data: list[dict] | None = None,
    row_ils: list[float] | None = None,
) -> openpyxl.Workbook:
    """Generate the full 12-sheet Excel workbook."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    sheets = {name: wb.create_sheet(name) for name in SHEET_NAMES}

    overpay_by_report: dict[int, float] = {}
    for row, res in zip(logistics_rows, overpayment_results):
        if res is not None and res.overpayment >= 0:
            rid = row.realizationreport_id
            overpay_by_report[rid] = overpay_by_report.get(rid, 0) + res.overpayment

    volumes = {nm: d["volume"] for nm, d in card_dims.items()}

    write_overpayment_formulas(
        sheets["Переплата по логистике (короб)"], logistics_rows,
        ktr=config.ktr, base_1l=46.0, extra_l=14.0,
        row_ils=row_ils,
    )
    write_overpayment_values(
        sheets["Переплата по логистике"], logistics_rows,
        overpayment_results, volumes, coefs, row_ils=row_ils,
    )
    write_svod(sheets["СВОД"], all_rows, overpay_by_report)
    write_detail(sheets["Детализация"], all_rows)
    write_il(sheets["ИЛ"], il_data)
    write_pivot_by_article(sheets["Переплата по артикулам"], logistics_rows, overpayment_results)
    write_logistics_types(sheets["Виды логистики"], logistics_rows)
    write_weekly(sheets["Еженед. отчет"], all_rows)
    write_dimensions(sheets["Габариты в карточке"], card_dims)
    write_tariffs_box(sheets["Тарифы короб"], tariffs_box)
    write_tariffs_pallet(sheets["Тариф монопалета"], tariffs_pallet)
    write_recommendations(
        sheets["Рекомендации"], logistics_rows, overpayment_results,
        config.date_from, config.date_to,
    )
    return wb
