from datetime import date
from unittest.mock import patch, MagicMock
from audit.calculators.warehouse_coef_resolver import (
    resolve_warehouse_coef,
    CoefResult,
    load_supabase_tariffs,
)


def test_resolve_fixation_tier():
    result = resolve_warehouse_coef(
        dlv_prc=100.0, fixed_coef=95.0,
        fixation_end=date(2026, 6, 1),
        order_date=date(2026, 3, 1),
        warehouse_name="Коледино",
        supabase_tariffs={},
    )
    assert result.source == "fixation"
    assert result.value == 95.0
    assert result.verified is True


def test_resolve_fixation_expired():
    """fixation_end <= order_date → fixation NOT used."""
    supabase = {"Коледино": {date(2026, 3, 1): 1.0}}
    result = resolve_warehouse_coef(
        dlv_prc=100.0, fixed_coef=95.0,
        fixation_end=date(2026, 3, 1),
        order_date=date(2026, 3, 1),
        warehouse_name="Коледино",
        supabase_tariffs=supabase,
    )
    assert result.source == "supabase"


def test_resolve_supabase_tier_closest_date():
    supabase = {
        "Коледино": {
            date(2026, 3, 1): 0.95,
            date(2026, 3, 10): 1.05,
        }
    }
    result = resolve_warehouse_coef(
        dlv_prc=0.0, fixed_coef=0.0,
        fixation_end=None, order_date=date(2026, 3, 15),
        warehouse_name="Коледино", supabase_tariffs=supabase,
    )
    assert result.source == "supabase"
    assert result.value == 1.05
    assert result.verified is True


def test_resolve_dlv_prc_fallback():
    result = resolve_warehouse_coef(
        dlv_prc=1.2, fixed_coef=0.0,
        fixation_end=None, order_date=date(2026, 3, 15),
        warehouse_name="НеизвестныйСклад",
        supabase_tariffs={},
    )
    assert result.source == "dlv_prc"
    assert result.verified is False
    assert result.value == 1.2


def test_resolve_zero_coef_fallback():
    """All tiers fail → CoefResult(0.0, dlv_prc, False)."""
    result = resolve_warehouse_coef(
        dlv_prc=0.0, fixed_coef=0.0,
        fixation_end=None, order_date=None,
        warehouse_name="НеизвестныйСклад",
        supabase_tariffs={},
    )
    assert result.value == 0.0


def test_load_supabase_tariffs_calls_client():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.gte.return_value.lte.return_value.execute.return_value.data = [
        {"warehouse_name": "Коледино", "dt": "2026-03-15", "delivery_coef": 95},
    ]
    with patch("audit.calculators.warehouse_coef_resolver.get_supabase_client", return_value=mock_client):
        result = load_supabase_tariffs(date(2026, 3, 1), date(2026, 3, 31))
    assert "Коледино" in result
    assert result["Коледино"][date(2026, 3, 15)] == 0.95
