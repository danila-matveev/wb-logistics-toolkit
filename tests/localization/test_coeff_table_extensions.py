# tests/localization/test_coeff_table_extensions.py
import pytest
from unittest.mock import patch

import shared.coeff_table as ct

MOCK_ROWS = [
    {"min_loc": 80.0, "max_loc": 84.99, "ktr": 0.80, "krp_pct": 0.0},
    {"min_loc": 60.0, "max_loc": 64.99, "ktr": 1.00, "krp_pct": 0.0},
    {"min_loc": 0.0,  "max_loc":  4.99, "ktr": 2.20, "krp_pct": 2.50},
]


@pytest.fixture(autouse=True)
def clear():
    ct.clear_cache()
    yield
    ct.clear_cache()


def mock_sb(rows):
    from unittest.mock import MagicMock
    m = MagicMock()
    m.table.return_value.select.return_value \
        .lte.return_value.order.return_value.execute.return_value.data = rows
    return m


def test_get_coeff_table_returns_list_of_dicts():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_sb(MOCK_ROWS)):
        table = ct.get_coeff_table()
    assert isinstance(table, list)
    assert len(table) == 3
    assert "min_loc" in table[0]
    assert "max_loc" in table[0]
    assert "ktr" in table[0]
    assert "krp_pct" in table[0]


def test_get_coeff_table_same_object_as_get_ktr_krp():
    """get_coeff_table() must share the same cache as get_ktr_krp()."""
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_sb(MOCK_ROWS)) as mock:
        ct.get_ktr_krp(80.0)
        ct.get_coeff_table()
    assert mock.return_value.table.call_count == 1


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
