from __future__ import annotations
from dataclasses import dataclass
from datetime import date

from shared.coeff_table import get_ktr_krp

FORMULA_CHANGE_DATE = date(2026, 3, 23)


@dataclass
class OverpaymentResult:
    calculated_cost: float
    overpayment: float


def calculate_row_overpayment(
    delivery_rub: float,
    volume: float,
    coef: float,
    base_1l: float,
    extra_l: float,
    order_dt: date | None,
    ktr_manual: float,
    is_fixed_rate: bool,
    is_forward_delivery: bool = True,
    sku_localization_pct: float | None = None,
    retail_price: float = 0.0,
) -> OverpaymentResult | None:
    """Calculate overpayment for a single logistics row.

    Uses old formula (KTR) before 23.03.2026,
    new formula (IL + IRP) from 23.03.2026.
    Returns None if row is not auditable (non-forward, zero coef).
    """
    if is_fixed_rate:
        return OverpaymentResult(calculated_cost=delivery_rub, overpayment=0.0)

    if not is_forward_delivery:
        return None

    if coef == 0:
        return None

    if volume > 1:
        base_cost = (base_1l + (volume - 1) * extra_l) * coef
    else:
        base_cost = base_1l * coef

    use_new_formula = order_dt and order_dt >= FORMULA_CHANGE_DATE

    if use_new_formula and sku_localization_pct is not None:
        il, irp_pct = get_ktr_krp(sku_localization_pct)
        cost = base_cost * il + retail_price * (irp_pct / 100)
    else:
        cost = base_cost * ktr_manual

    cost = round(cost, 2)
    return OverpaymentResult(
        calculated_cost=cost,
        overpayment=round(delivery_rub - cost, 2),
    )
