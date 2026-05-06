# tests/shared/test_coeff_table.py
import pytest
from unittest.mock import patch, MagicMock

import shared.coeff_table as ct


MOCK_ROWS = [
    {"min_loc": 95.0, "max_loc": 100.0, "ktr": 0.50, "krp_pct": 0.0},
    {"min_loc": 80.0, "max_loc": 84.99, "ktr": 0.80, "krp_pct": 0.0},
    {"min_loc": 60.0, "max_loc": 64.99, "ktr": 1.00, "krp_pct": 0.0},
    {"min_loc": 55.0, "max_loc": 59.99, "ktr": 1.05, "krp_pct": 2.00},
    {"min_loc": 0.0,  "max_loc":  4.99, "ktr": 2.20, "krp_pct": 2.50},
]


@pytest.fixture(autouse=True)
def clear_cache():
    ct.clear_cache()
    yield
    ct.clear_cache()


def mock_supabase(rows):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value \
        .lte.return_value.order.return_value.execute.return_value.data = rows
    return mock_client


def test_get_ktr_krp_high_localization():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(97.0)
    assert ktr == 0.50
    assert krp == 0.0


def test_get_ktr_krp_at_80_percent():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(82.0)
    assert ktr == 0.80
    assert krp == 0.0


def test_get_ktr_krp_at_irp_zone():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(57.0)
    assert ktr == 1.05
    assert krp == 2.00


def test_get_ktr_krp_zero_localization():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(0.0)
    assert ktr == 2.20
    assert krp == 2.50


def test_get_ktr_krp_uses_cache_on_second_call():
    mock_sb = mock_supabase(MOCK_ROWS)
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_sb):
        ct.get_ktr_krp(80.0)
        ct.get_ktr_krp(60.0)
    # Supabase should only be called once due to caching
    assert mock_sb.table.call_count == 1


def test_raises_if_table_empty():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase([])):
        with pytest.raises(RuntimeError, match="wb_coeff_table is empty"):
            ct.get_ktr_krp(50.0)


def test_clamp_above_100():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(150.0)
    assert ktr == 0.50


def test_clamp_below_0():
    with patch("shared.coeff_table.get_supabase_client", return_value=mock_supabase(MOCK_ROWS)):
        ktr, krp = ct.get_ktr_krp(-10.0)
    assert ktr == 2.20
