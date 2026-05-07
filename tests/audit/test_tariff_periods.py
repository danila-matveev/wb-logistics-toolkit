from datetime import date
from audit.calculators.tariff_periods import get_base_tariffs


def test_latest_period_standard_volume():
    """2025-10-01 with vol=2L → standard 46+14 (after SUB_LITER_START, but vol≥1)."""
    base, extra = get_base_tariffs(date(2025, 10, 1), None, None, 2.0)
    assert base == 46.0
    assert extra == 14.0


def test_sub_liter_tier_03():
    """2025-10-01 with vol=0.3L → tier (max_vol=0.4): 26+0."""
    base, extra = get_base_tariffs(date(2025, 10, 1), None, None, 0.3)
    assert base == 26.0
    assert extra == 0.0


def test_sub_liter_tier_02():
    """vol=0.15L → tier (max_vol=0.2): 23+0."""
    base, extra = get_base_tariffs(date(2025, 10, 1), None, None, 0.15)
    assert base == 23.0
    assert extra == 0.0


def test_sub_liter_before_start_date_ignored():
    """Sub-liter tiers only apply from 22.09.2025. Earlier date → standard period."""
    base, extra = get_base_tariffs(date(2025, 9, 1), None, None, 0.3)
    assert base == 38.0  # standard period 28.02.2025
    assert extra == 9.5


def test_period_2025_02_28():
    base, extra = get_base_tariffs(date(2025, 3, 1), None, None, 2.0)
    assert base == 38.0
    assert extra == 9.5


def test_period_2024_12_11():
    base, extra = get_base_tariffs(date(2024, 12, 15), None, None, 2.0)
    assert base == 35.0
    assert extra == 8.5


def test_period_2024_08_14():
    base, extra = get_base_tariffs(date(2024, 8, 20), None, None, 2.0)
    assert base == 33.0
    assert extra == 8.0


def test_fixation_uses_fixation_start():
    """When fixation active, tariff period determined by fixation_start."""
    base, extra = get_base_tariffs(
        order_date=date(2025, 10, 1),
        fixation_start=date(2024, 8, 20),
        fixation_end=date(2025, 12, 31),
        volume=2.0,
    )
    # fixation_start=2024-08-20 → period 2024-08-14: 33+8
    assert base == 33.0
    assert extra == 8.0
