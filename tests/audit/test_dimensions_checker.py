from audit.calculators.dimensions_checker import check_dimensions


def test_check_dimensions_flags_large_diff():
    card_dims = {1: 10.0}
    wb_volumes = {1: 12.5}
    results = check_dimensions(card_dims, wb_volumes, threshold_pct=10.0)
    assert results[1].flagged is True
    assert abs(results[1].pct_diff - 25.0) < 0.01


def test_check_dimensions_no_flag_within_threshold():
    card_dims = {1: 10.0}
    wb_volumes = {1: 10.5}
    results = check_dimensions(card_dims, wb_volumes, threshold_pct=10.0)
    assert results[1].flagged is False


def test_check_dimensions_skips_missing_wb_volume():
    card_dims = {1: 10.0, 2: 5.0}
    wb_volumes = {1: 11.0}
    results = check_dimensions(card_dims, wb_volumes)
    assert 2 not in results


def test_check_dimensions_skips_zero_card_volume():
    card_dims = {1: 0.0}
    wb_volumes = {1: 5.0}
    results = check_dimensions(card_dims, wb_volumes)
    assert 1 not in results
