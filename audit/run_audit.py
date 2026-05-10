"""Logistics audit pipeline: fetch → calculate → Excel.

Usage:
    python audit/run_audit.py ooo 2026-01-01 2026-03-31
    python audit/run_audit.py ooo 2026-01-01 2026-03-31 --ktr 0.9
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import get_cabinet
from shared.wb_api.client import WBClient
from shared.wb_api.reports import fetch_report
from shared.wb_api.tariffs import fetch_box_tariffs, fetch_pallet_tariffs
from shared.wb_api.content import fetch_card_dimensions
from shared.wb_api.orders import fetch_orders
from shared.wb_api.warehouse_remains import fetch_warehouse_remains
from shared.wb_api.penalties import fetch_measurement_penalties, fetch_deductions
from audit.models.audit_config import AuditConfig
from audit.models.report_row import ReportRow
from audit.models.tariff_snapshot import TariffSnapshot
from audit.calculators.tariff_periods import get_base_tariffs
from audit.calculators.warehouse_coef_resolver import resolve_warehouse_coef, load_tariffs
from audit.calculators.logistics_overpayment import (
    calculate_row_overpayment, OverpaymentResult, FORMULA_CHANGE_DATE,
)
from audit.calculators.weekly_il_calculator import calculate_weekly_il, get_il_for_date
from audit.calculators.localization_resolver import calculate_sku_localization
from audit.output.excel_generator import generate_workbook

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WB Logistics Audit")
    parser.add_argument("cabinet", help="Cabinet name (matches cabinets.yaml)")
    parser.add_argument("date_from", help="Audit start date YYYY-MM-DD")
    parser.add_argument("date_to", help="Audit end date YYYY-MM-DD")
    parser.add_argument("--ktr", type=float, default=1.0, help="Manual KTR override (default 1.0)")
    parser.add_argument("--output-dir", type=str, default=".", help="Output directory for Excel")
    return parser.parse_args(argv)


def run_audit(config: AuditConfig, output_dir: str = ".") -> str:
    """Run full logistics audit pipeline. Returns path to generated Excel file."""
    df = config.date_from.isoformat()
    dt = config.date_to.isoformat()
    logger.info("Starting audit: %s → %s, cabinet=%s", df, dt, config.cabinet)

    client = WBClient(token=config.api_key)

    # Step 1: Fetch all data
    logger.info("Fetching reportDetailByPeriod...")
    raw_rows = fetch_report(client, df, dt)
    all_rows = [ReportRow.from_api(d) for d in raw_rows]
    logger.info("Total rows: %d", len(all_rows))

    logger.info("Fetching tariffs...")
    raw_box = fetch_box_tariffs(client, dt)
    tariffs_box: dict[str, TariffSnapshot] = {
        TariffSnapshot.from_api(d).warehouse_name: TariffSnapshot.from_api(d)
        for d in raw_box
    }
    tariffs_pallet = fetch_pallet_tariffs(client, dt)

    logger.info("Fetching card dimensions...")
    nm_ids = list({row.nm_id for row in all_rows if row.nm_id})
    card_dims: dict[int, dict] = fetch_card_dimensions(client, nm_ids)

    logger.info("Fetching warehouse remains...")
    wb_volumes_raw = fetch_warehouse_remains(client)
    wb_volumes: dict[int, float] = {}
    for item in wb_volumes_raw:
        nm_id = item.get("nmId", 0)
        if nm_id:
            wb_volumes[nm_id] = float(item.get("volume", 0))

    logger.info("Fetching penalties...")
    dt_rfc3339 = f"{dt}T23:59:59Z"
    penalties = fetch_measurement_penalties(client, dt_rfc3339)
    deductions = fetch_deductions(client, dt_rfc3339)
    logger.info("Penalties: %d, Deductions: %d", len(penalties), len(deductions))

    # Step 2: Filter logistics rows
    logistics_rows = [r for r in all_rows if r.is_logistics]
    logger.info("Logistics rows: %d", len(logistics_rows))

    # Step 3: Weekly IL from orders
    logger.info("Fetching orders for weekly IL...")
    orders_from = (config.date_from - timedelta(days=7)).isoformat()
    orders = fetch_orders(client, orders_from)
    logger.info("Orders fetched: %d", len(orders))
    week_to_il, il_data = calculate_weekly_il(orders, config.date_from, config.date_to)

    # Step 4: Per-SKU localization (for new formula rows >= 23.03.2026)
    has_new_formula = any(
        r.order_dt and r.order_dt >= FORMULA_CHANGE_DATE for r in logistics_rows
    )
    sku_localization: dict[int, float] = {}
    prices: dict[int, float] = {}
    if has_new_formula:
        logger.info("New formula rows detected, calculating per-SKU localization...")
        sku_localization = calculate_sku_localization(orders)
        logger.info("Localization data for %d SKUs", len(sku_localization))

    # Step 5: Load historical tariffs from SQLite
    logger.info("Loading historical tariffs...")
    tariffs = load_tariffs(config.date_from, config.date_to)

    # Step 6: Calculate per-row overpayments
    results: list[OverpaymentResult | None] = []
    coefs: list[float] = []
    row_ils: list[float] = []

    for row in logistics_rows:
        vol = card_dims.get(row.nm_id, {}).get("volume", 0)

        coef_result = resolve_warehouse_coef(
            dlv_prc=row.dlv_prc,
            fixed_coef=row.dlv_prc,
            fixation_end=row.fix_tariff_date_to,
            order_date=row.order_dt,
            warehouse_name=row.office_name,
            tariffs=tariffs,
        )
        coefs.append(coef_result.value)

        base_1l, extra_l = get_base_tariffs(
            order_date=row.order_dt,
            fixation_start=row.fix_tariff_date_from,
            fixation_end=row.fix_tariff_date_to,
            volume=vol,
        )

        row_il = get_il_for_date(week_to_il, row.order_dt)
        if row_il is None:
            row_il = config.ktr if config.ktr > 0 else 1.0
        row_ils.append(row_il)

        result = calculate_row_overpayment(
            delivery_rub=row.delivery_rub,
            volume=vol,
            coef=coef_result.value,
            base_1l=base_1l,
            extra_l=extra_l,
            order_dt=row.order_dt,
            ktr_manual=row_il,
            is_fixed_rate=row.is_fixed_rate,
            is_forward_delivery=row.is_forward_delivery,
            sku_localization_pct=sku_localization.get(row.nm_id),
            retail_price=prices.get(row.nm_id, 0.0),
        )
        results.append(result)

    total_charged = sum(r.delivery_rub for r in logistics_rows)
    if total_charged > 0:
        total_overpay = sum(res.overpayment for res in results if res is not None)
        logger.info(
            "WB charged: %.2f₽ | Calculated overpayment: %.2f₽ (%.1f%%)",
            total_charged, total_overpay, total_overpay / total_charged * 100,
        )

    # Step 7: Generate Excel
    wb = generate_workbook(
        config=config,
        all_rows=all_rows,
        logistics_rows=logistics_rows,
        overpayment_results=results,
        coefs=coefs,
        card_dims=card_dims,
        tariffs_box=tariffs_box,
        tariffs_pallet=tariffs_pallet,
        wb_volumes=wb_volumes,
        il_data=il_data,
        row_ils=row_ils,
    )

    filename = f"Аудит логистики {df} — {dt}.xlsx"
    filepath = str(Path(output_dir) / filename)
    wb.save(filepath)
    logger.info("Excel saved: %s", filepath)
    return filepath


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    cab = get_cabinet(args.cabinet)
    config = AuditConfig(
        api_key=cab.wb_token,
        date_from=date.fromisoformat(args.date_from),
        date_to=date.fromisoformat(args.date_to),
        ktr=args.ktr,
        cabinet=args.cabinet,
    )
    output = run_audit(config, output_dir=args.output_dir)
    print(f"Done: {output}")


if __name__ == "__main__":
    main()
