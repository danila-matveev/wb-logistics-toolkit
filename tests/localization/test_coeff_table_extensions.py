# tests/localization/test_coeff_table_extensions.py
import pytest

import shared.coeff_table as ct


def test_get_coeff_table_returns_list_of_dicts():
    table = ct.get_coeff_table()
    assert isinstance(table, list)
    assert len(table) == 20
    assert "min_loc" in table[0]
    assert "max_loc" in table[0]
    assert "ktr" in table[0]
    assert "krp_pct" in table[0]


def test_get_coeff_table_same_object_as_get_ktr_krp():
    """get_coeff_table() must return the same embedded list used by get_ktr_krp()."""
    assert ct.get_coeff_table() is ct.COEFF_TABLE


def test_calc_financial_impact_basic():
    # krp_pct=2.0, price=1000, orders=30, period_days=30
    # monthly_orders = (30/30)*30 = 30
    # impact = 2.0/100 * 1000 * 30 = 600.0
    assert ct.calc_financial_impact(2.0, 1000.0, 30, 30) == pytest.approx(600.0)


def test_calc_financial_impact_zero_krp():
    assert ct.calc_financial_impact(0.0, 1000.0, 30, 30) == 0.0


def test_calc_financial_impact_zero_price():
    assert ct.calc_financial_impact(2.0, 0.0, 30, 30) == 0.0


def test_calc_financial_impact_zero_orders():
    assert ct.calc_financial_impact(2.0, 1000.0, 0, 30) == 0.0


def test_calc_financial_impact_zero_period():
    assert ct.calc_financial_impact(2.0, 1000.0, 30, 0) == 0.0


def test_calc_financial_impact_short_period():
    # orders=10, period_days=7 → daily=10/7, monthly=10/7*30≈42.857
    # impact = 2.0/100 * 1000 * (10/7*30) ≈ 857.14
    result = ct.calc_financial_impact(2.0, 1000.0, 10, 7)
    assert result == pytest.approx(2.0 / 100 * 1000 * (10 / 7 * 30), rel=1e-4)
