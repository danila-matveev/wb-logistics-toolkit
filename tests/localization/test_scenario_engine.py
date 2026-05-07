# tests/localization/test_scenario_engine.py
import pytest
from unittest.mock import patch

MOCK_ROWS = [
    {"min_loc": 80.0, "max_loc": 84.99, "ktr": 0.80, "krp_pct": 0.0},
    {"min_loc": 60.0, "max_loc": 64.99, "ktr": 1.00, "krp_pct": 0.0},
    {"min_loc": 55.0, "max_loc": 59.99, "ktr": 1.05, "krp_pct": 2.00},
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


def test_ktr_to_loc_pct_finds_midpoint():
    from localization.calculators.scenario_engine import _ktr_to_loc_pct
    result = _ktr_to_loc_pct(0.80)
    assert result == pytest.approx((80.0 + 84.99) / 2)


def test_ktr_to_loc_pct_fallback():
    from localization.calculators.scenario_engine import _ktr_to_loc_pct
    result = _ktr_to_loc_pct(99.0)  # higher than any KTR → fallback
    assert result == 0.0


def test_analyze_scenarios_structure():
    from localization.calculators.scenario_engine import analyze_scenarios
    il_irp = {
        "articles": [{
            "article": "art-a", "ktr": 1.30, "krp_pct": 2.10,
            "wb_total": 10, "price": 1000.0,
            "loc_pct": 40.0, "irp_per_month": 100.0,
        }],
        "summary": {"overall_il": 1.30},
    }
    logistics_costs = {"art-a": 500.0}
    result = analyze_scenarios(il_irp, logistics_costs, turnover_rub=100_000)
    assert "scenarios" in result
    assert "top_articles" in result
    assert "relocation_economics" in result
    assert len(result["scenarios"]) == 7  # default levels


def test_analyze_scenarios_custom_levels():
    from localization.calculators.scenario_engine import analyze_scenarios
    il_irp = {"articles": [], "summary": {"overall_il": 1.0}}
    result = analyze_scenarios(il_irp, {}, 50_000, levels=[70.0, 80.0])
    assert len(result["scenarios"]) == 2
