from datetime import date
from unittest.mock import patch
from audit.calculators.logistics_overpayment import (
    calculate_row_overpayment,
    OverpaymentResult,
    FORMULA_CHANGE_DATE,
)


def test_formula_change_date():
    assert FORMULA_CHANGE_DATE == date(2026, 3, 23)


def test_fixed_rate_returns_zero_overpayment():
    result = calculate_row_overpayment(
        delivery_rub=100.0, volume=2.0, coef=1.0,
        base_1l=46.0, extra_l=14.0,
        order_dt=date(2025, 1, 1), ktr_manual=1.0,
        is_fixed_rate=True, is_forward_delivery=False,
    )
    assert result.overpayment == 0.0
    assert result.calculated_cost == 100.0


def test_non_forward_returns_none():
    result = calculate_row_overpayment(
        delivery_rub=100.0, volume=2.0, coef=1.0,
        base_1l=46.0, extra_l=14.0,
        order_dt=date(2025, 1, 1), ktr_manual=1.0,
        is_fixed_rate=False, is_forward_delivery=False,
    )
    assert result is None


def test_zero_coef_returns_none():
    result = calculate_row_overpayment(
        delivery_rub=100.0, volume=2.0, coef=0.0,
        base_1l=46.0, extra_l=14.0,
        order_dt=date(2025, 1, 1), ktr_manual=1.0,
        is_fixed_rate=False, is_forward_delivery=True,
    )
    assert result is None


def test_old_formula_basic():
    """Old formula (before 23.03.2026): cost = (46 + 1×14) × 1.0 × 1.0 = 60."""
    result = calculate_row_overpayment(
        delivery_rub=100.0, volume=2.0, coef=1.0,
        base_1l=46.0, extra_l=14.0,
        order_dt=date(2025, 1, 1), ktr_manual=1.0,
        is_fixed_rate=False, is_forward_delivery=True,
    )
    assert result is not None
    assert result.calculated_cost == 60.0
    assert result.overpayment == 40.0


def test_new_formula_uses_get_ktr_krp():
    """New formula (>=23.03.2026): uses get_ktr_krp from shared.coeff_table."""
    with patch(
        "audit.calculators.logistics_overpayment.get_ktr_krp",
        return_value=(0.8, 0.0),
    ):
        result = calculate_row_overpayment(
            delivery_rub=100.0, volume=2.0, coef=1.0,
            base_1l=46.0, extra_l=14.0,
            order_dt=date(2026, 4, 1), ktr_manual=1.0,
            is_fixed_rate=False, is_forward_delivery=True,
            sku_localization_pct=85.0, retail_price=500.0,
        )
    # base_cost = (46 + 1×14) × 1.0 = 60; cost = 60 × 0.8 + 500 × 0.0 = 48
    assert result is not None
    assert result.calculated_cost == 48.0
