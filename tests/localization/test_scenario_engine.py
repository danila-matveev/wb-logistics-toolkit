# tests/localization/test_scenario_engine.py
import pytest


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
