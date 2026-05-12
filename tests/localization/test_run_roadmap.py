from unittest.mock import MagicMock, patch
from pathlib import Path

from localization.run_roadmap import _parse_args, run_roadmap


def test_parse_args_basic():
    args = _parse_args(["ooo"])
    assert args.cabinet == "ooo"
    assert args.target == 85.0
    assert args.limit == 0.3
    assert args.no_sheets is False


def test_parse_args_with_target_and_no_sheets():
    args = _parse_args(["ooo", "--target", "90", "--limit", "0.5", "--no-sheets"])
    assert args.cabinet == "ooo"
    assert args.target == 90.0
    assert args.limit == 0.5
    assert args.no_sheets is True


def test_run_roadmap_returns_excel_path_when_no_sheets(tmp_path):
    fake_cache = {
        "il_irp": {
            "articles": [
                {"article": "X", "wb_local": 50, "wb_total": 100, "loc_pct": 50.0,
                 "ktr": 0.7, "krp_pct": 70.0},
            ],
        },
        "logistics_costs": {"total_monthly": 1000.0},
        "period_days": 60,
    }
    fake_cabinet = MagicMock(wb_token="tok", sheet_id="")
    fake_roadmap = {
        "milestones": {"week_60pct": 5, "week_80pct": 10},
        "params": {"target_localization": 85, "realistic_limit_pct": 0.3},
        "roadmap": [{"week": 1, "date": "2026-05-12"}],
    }
    fake_perm = {"movements": []}

    with patch("localization.run_roadmap.load_cache", return_value=fake_cache), \
         patch("localization.run_roadmap.get_cabinet", return_value=fake_cabinet), \
         patch("localization.run_roadmap.WBClient"), \
         patch("localization.run_roadmap.load_warehouse_statuses", return_value={}), \
         patch("localization.run_roadmap.fetch_warehouse_remains", return_value=[]), \
         patch("localization.run_roadmap.generate_movements", return_value=fake_perm), \
         patch("localization.run_roadmap.simulate_roadmap", return_value=fake_roadmap):
        path = run_roadmap(
            cabinet_name="ooo",
            no_sheets=True,
            output_dir=str(tmp_path),
        )

    assert path is not None
    assert "Roadmap" in path
    assert path.endswith(".xlsx")
    assert Path(path).exists()


def test_run_roadmap_exits_when_no_cache(tmp_path):
    import pytest
    with patch("localization.run_roadmap.load_cache", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            run_roadmap(
                cabinet_name="missing",
                no_sheets=True,
                output_dir=str(tmp_path),
            )
        assert exc_info.value.code == 1
