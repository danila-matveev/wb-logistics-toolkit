from datetime import date
from audit.calculators.warehouse_coef_resolver import (
    resolve_warehouse_coef,
    CoefResult,
    load_tariffs,
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
    tariffs = {"Коледино": {date(2026, 3, 1): 1.0}}
    result = resolve_warehouse_coef(
        dlv_prc=100.0, fixed_coef=95.0,
        fixation_end=date(2026, 3, 1),
        order_date=date(2026, 3, 1),
        warehouse_name="Коледино",
        supabase_tariffs=tariffs,
    )
    assert result.source == "sqlite"


def test_resolve_sqlite_tier_closest_date():
    tariffs = {
        "Коледино": {
            date(2026, 3, 1): 0.95,
            date(2026, 3, 10): 1.05,
        }
    }
    result = resolve_warehouse_coef(
        dlv_prc=0.0, fixed_coef=0.0,
        fixation_end=None, order_date=date(2026, 3, 15),
        warehouse_name="Коледино", supabase_tariffs=tariffs,
    )
    assert result.source == "sqlite"
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


def test_load_tariffs_reads_from_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    from shared import db as db_module
    db_module._reset_for_tests()

    conn = db_module.get_connection()
    conn.executemany(
        "INSERT INTO wb_tariffs (dt, warehouse_name, delivery_coef) VALUES (?, ?, ?)",
        [
            ("2026-04-01", "Коледино", 95.0),
            ("2026-04-15", "Коледино", 100.0),
            ("2026-04-10", "Электросталь", 110.0),
            ("2026-03-01", "OutOfRange", 90.0),
        ],
    )
    conn.commit()

    result = load_tariffs(date(2026, 4, 1), date(2026, 4, 30))

    assert "Коледино" in result
    assert result["Коледино"][date(2026, 4, 1)] == 0.95
    assert result["Коледино"][date(2026, 4, 15)] == 1.00
    assert result["Электросталь"][date(2026, 4, 10)] == 1.10
    assert "OutOfRange" not in result

    db_module._reset_for_tests()


def test_load_tariffs_empty_db_returns_empty(tmp_path, monkeypatch):
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    from shared import db as db_module
    db_module._reset_for_tests()
    result = load_tariffs(date(2026, 1, 1), date(2026, 12, 31))
    assert result == {}
    db_module._reset_for_tests()
