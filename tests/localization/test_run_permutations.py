from unittest.mock import MagicMock, patch
from pathlib import Path

from localization.run_permutations import _parse_args, run_permutations


def test_parse_args_basic():
    args = _parse_args(["ooo"])
    assert args.cabinet == "ooo"
    assert args.safety_days == 14
    assert args.no_sheets is False


def test_parse_args_with_safety_and_no_sheets():
    args = _parse_args(["ooo", "--safety-days", "7", "--no-sheets"])
    assert args.cabinet == "ooo"
    assert args.safety_days == 7
    assert args.no_sheets is True


def test_run_permutations_returns_excel_path_when_no_sheets(tmp_path):
    fake_cache = {
        "il_irp": {
            "articles": [
                {"article": "X", "wb_local": 50, "wb_total": 100, "loc_pct": 50.0},
            ],
        },
        "period_days": 60,
    }
    fake_cabinet = MagicMock(wb_token="tok", sheet_id="")
    fake_result = {
        "movements": [{"article": "X", "from_fd": "ЦФО", "from_warehouse": "Коледино",
                       "to_fd": "СЗФО", "to_warehouse": "СПб", "qty": 10}],
        "supplies": [],
        "region_summary": [
            {"fd": "ЦФО", "stock_total": 100, "orders_total": 50, "loc_pct": 80.0}
        ],
    }

    with patch("localization.run_permutations.load_cache", return_value=fake_cache), \
         patch("localization.run_permutations.get_cabinet", return_value=fake_cabinet), \
         patch("localization.run_permutations.WBClient"), \
         patch("localization.run_permutations.load_warehouse_statuses", return_value={}), \
         patch("localization.run_permutations.fetch_warehouse_remains", return_value=[]), \
         patch("localization.run_permutations.generate_movements", return_value=fake_result):
        path = run_permutations(
            cabinet_name="ooo",
            no_sheets=True,
            output_dir=str(tmp_path),
        )

    assert path is not None
    assert "Перестановки" in path
    assert path.endswith(".xlsx")
    assert Path(path).exists()


def test_run_permutations_exits_when_no_cache(tmp_path):
    import pytest
    with patch("localization.run_permutations.load_cache", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            run_permutations(
                cabinet_name="missing",
                no_sheets=True,
                output_dir=str(tmp_path),
            )
        assert exc_info.value.code == 1
