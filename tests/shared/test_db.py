# tests/shared/test_db.py
import sqlite3
from pathlib import Path

import pytest

from shared import db as db_module


@pytest.fixture(autouse=True)
def reset_singleton(monkeypatch, tmp_path):
    """Force a fresh DB path and clear cached connection between tests."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    db_module._reset_for_tests()
    yield
    db_module._reset_for_tests()


def test_get_connection_creates_db_file(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    db_module._reset_for_tests()
    conn = db_module.get_connection()
    assert db_path.exists()
    assert isinstance(conn, sqlite3.Connection)


def test_get_connection_creates_wb_tariffs_table():
    conn = db_module.get_connection()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='wb_tariffs'"
    )
    assert cur.fetchone() is not None


def test_wb_tariffs_columns_match_spec():
    conn = db_module.get_connection()
    cur = conn.execute("PRAGMA table_info(wb_tariffs)")
    cols = {row[1]: row[2] for row in cur.fetchall()}
    assert cols == {
        "dt": "TEXT",
        "warehouse_name": "TEXT",
        "delivery_coef": "REAL",
        "logistics_1l": "REAL",
        "logistics_extra_l": "REAL",
        "box_storage_base": "REAL",
        "storage_coef": "REAL",
        "geo_name": "TEXT",
        "created_at": "TEXT",
    }


def test_wb_tariffs_primary_key_is_dt_warehouse():
    conn = db_module.get_connection()
    pk_cols_sorted_by_pk_index = sorted(
        [(row[1], row[5]) for row in conn.execute("PRAGMA table_info(wb_tariffs)") if row[5] > 0],
        key=lambda x: x[1],
    )
    assert [c for c, _ in pk_cols_sorted_by_pk_index] == ["dt", "warehouse_name"]


def test_journal_mode_is_wal():
    conn = db_module.get_connection()
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_get_connection_returns_same_instance():
    conn1 = db_module.get_connection()
    conn2 = db_module.get_connection()
    assert conn1 is conn2


def test_default_path_when_env_var_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WB_TOOLKIT_DB_PATH", raising=False)
    db_module._reset_for_tests()
    db_module.get_connection()
    assert (tmp_path / "data" / "wb_toolkit.db").exists()
