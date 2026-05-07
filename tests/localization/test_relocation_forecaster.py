# tests/localization/test_relocation_forecaster.py
import pytest
from datetime import date
from unittest.mock import patch

MOCK_ROWS = [
    {"min_loc": 80.0, "max_loc": 84.99, "ktr": 0.80, "krp_pct": 0.0},
    {"min_loc": 60.0, "max_loc": 64.99, "ktr": 1.00, "krp_pct": 0.0},
    {"min_loc":  0.0, "max_loc":  4.99, "ktr": 2.20, "krp_pct": 2.50},
]


@pytest.fixture(autouse=True)
def patch_coeff():
    import shared.coeff_table as ct
    ct.clear_cache()
    from unittest.mock import MagicMock
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value \
        .lte.return_value.order.return_value.execute.return_value.data = MOCK_ROWS
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_sb):
        yield
    ct.clear_cache()


def test_simulate_roadmap_returns_14_weeks():
    from localization.calculators.relocation_forecaster import simulate_roadmap
    articles = [{
        "article": "art-a", "loc_pct": 40.0, "ktr": 1.30, "krp_pct": 2.10,
        "wb_total": 30, "price": 1000.0, "stock_total": 100,
    }]
    result = simulate_roadmap(
        articles=articles,
        movements=[],
        logistics_costs={"art-a": 1000.0},
        weekly_orders_history=[],
        redistribution_limits={},
        start_date=date(2026, 5, 6),
    )
    assert len(result["roadmap"]) == 14
    assert result["roadmap"][0]["week"] == 0
    assert result["roadmap"][13]["week"] == 13


def test_simulate_roadmap_week0_no_savings():
    from localization.calculators.relocation_forecaster import simulate_roadmap
    articles = [{
        "article": "art-a", "loc_pct": 40.0, "ktr": 1.30, "krp_pct": 2.10,
        "wb_total": 30, "price": 1000.0, "stock_total": 100,
    }]
    result = simulate_roadmap(
        articles=articles,
        movements=[],
        logistics_costs={"art-a": 500.0},
        weekly_orders_history=[],
        redistribution_limits={},
        start_date=date(2026, 5, 6),
    )
    assert result["roadmap"][0]["savings_vs_current"] == 0.0


def test_ktr_to_loc_pct_with_tolerance():
    from localization.calculators.relocation_forecaster import _ktr_to_loc_pct
    result = _ktr_to_loc_pct(0.80)
    assert result == pytest.approx((80.0 + 84.99) / 2)
