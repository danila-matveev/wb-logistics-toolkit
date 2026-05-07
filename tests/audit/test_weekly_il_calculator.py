from datetime import date
from unittest.mock import patch
from audit.calculators.weekly_il_calculator import (
    calculate_weekly_il,
    get_il_for_date,
)


def _monday(d: date) -> date:
    from datetime import timedelta
    return d - timedelta(days=d.weekday())


def test_all_keys_are_mondays():
    with patch(
        "audit.calculators.weekly_il_calculator.get_ktr_krp",
        return_value=(1.0, 0.0),
    ):
        week_to_il, _ = calculate_weekly_il([], date(2026, 1, 5), date(2026, 1, 18))
    assert all(d.weekday() == 0 for d in week_to_il)


def test_returns_il_for_period():
    """Two weeks in period → two keys in week_to_il."""
    with patch(
        "audit.calculators.weekly_il_calculator.get_ktr_krp",
        return_value=(1.0, 0.0),
    ):
        week_to_il, _ = calculate_weekly_il([], date(2026, 1, 5), date(2026, 1, 18))
    assert len(week_to_il) == 2


def test_get_il_for_date_returns_none_empty():
    assert get_il_for_date({}, date(2026, 1, 5)) is None


def test_get_il_for_date_returns_none_none_date():
    assert get_il_for_date({date(2026, 1, 5): 1.0}, None) is None


def test_get_il_for_date_looks_up_monday():
    mon = _monday(date(2026, 1, 7))  # wednesday → monday 2026-01-05
    week_to_il = {mon: 0.8}
    assert get_il_for_date(week_to_il, date(2026, 1, 7)) == 0.8
