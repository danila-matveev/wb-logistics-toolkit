# tests/shared/test_coeff_table.py
"""Tests for shared.coeff_table after Supabase removal — table is embedded."""
import pytest

from shared.coeff_table import COEFF_TABLE, get_ktr_krp, get_coeff_table, calc_financial_impact


def test_table_has_20_rows():
    assert len(COEFF_TABLE) == 20


def test_table_covers_full_0_100_range():
    sorted_rows = sorted(COEFF_TABLE, key=lambda r: r["min_loc"])
    assert sorted_rows[0]["min_loc"] == 0.0
    assert sorted_rows[-1]["max_loc"] == 100.0
    for prev, nxt in zip(sorted_rows, sorted_rows[1:]):
        assert nxt["min_loc"] > prev["max_loc"]
        assert nxt["min_loc"] - prev["max_loc"] < 0.02


def test_get_ktr_krp_high_localization():
    ktr, krp = get_ktr_krp(97.0)
    assert ktr == 0.50
    assert krp == 0.0


def test_get_ktr_krp_at_80_percent():
    ktr, krp = get_ktr_krp(82.0)
    assert ktr == 0.80
    assert krp == 0.0


def test_get_ktr_krp_at_irp_zone():
    ktr, krp = get_ktr_krp(57.0)
    assert ktr == 1.05
    assert krp == 2.00


def test_get_ktr_krp_zero_localization():
    ktr, krp = get_ktr_krp(0.0)
    assert ktr == 2.20
    assert krp == 2.50


def test_clamp_above_100():
    ktr, _ = get_ktr_krp(150.0)
    assert ktr == 0.50


def test_clamp_below_0():
    ktr, _ = get_ktr_krp(-10.0)
    assert ktr == 2.20


def test_get_coeff_table_returns_same_data():
    table = get_coeff_table()
    assert table is COEFF_TABLE


def test_calc_financial_impact_zero_inputs():
    assert calc_financial_impact(2.0, 0, 10, 30) == 0.0
    assert calc_financial_impact(2.0, 100, 0, 30) == 0.0


def test_calc_financial_impact_typical():
    impact = calc_financial_impact(krp_pct=2.0, price=1000.0, orders=300, period_days=30)
    assert impact == pytest.approx(2.0 / 100 * 1000 * 300, rel=1e-6)
