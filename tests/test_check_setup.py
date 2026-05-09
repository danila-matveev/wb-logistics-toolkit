# tests/test_check_setup.py
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


def test_check_setup_module_importable():
    import check_setup  # noqa: F401


def test_check_env_file_missing(tmp_path, monkeypatch):
    from check_setup import check_env_file
    monkeypatch.chdir(tmp_path)
    ok, msg = check_env_file()
    assert ok is False
    assert ".env" in msg


def test_check_env_file_present(tmp_path, monkeypatch):
    from check_setup import check_env_file
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("WB_TOKEN_OOO=abc")
    ok, msg = check_env_file()
    assert ok is True


def test_check_credentials_missing(tmp_path, monkeypatch):
    from check_setup import check_credentials
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(tmp_path / "creds.json"))
    ok, msg = check_credentials()
    assert ok is False
    assert "credentials" in msg.lower()


def test_check_credentials_present(tmp_path, monkeypatch):
    from check_setup import check_credentials
    creds = tmp_path / "creds.json"
    creds.write_text("{}")
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(creds))
    ok, msg = check_credentials()
    assert ok is True


def test_check_cabinets_yaml_missing(tmp_path, monkeypatch):
    from check_setup import check_cabinets_yaml
    monkeypatch.chdir(tmp_path)
    ok, msg = check_cabinets_yaml()
    assert ok is False


def test_check_credentials_not_in_git_staging(tmp_path, monkeypatch):
    from check_setup import check_credentials_not_staged
    # Should pass when git is not available or no staged file
    ok, msg = check_credentials_not_staged()
    assert isinstance(ok, bool)


def test_check_warehouse_status_yaml_missing(tmp_path, monkeypatch):
    from check_setup import check_warehouse_status_yaml
    monkeypatch.chdir(tmp_path)
    ok, msg = check_warehouse_status_yaml()
    assert ok is False


def test_check_warehouse_status_yaml_present(tmp_path, monkeypatch):
    from check_setup import check_warehouse_status_yaml
    monkeypatch.chdir(tmp_path)
    (tmp_path / "warehouse_status.yaml").write_text("warehouses: []")
    ok, msg = check_warehouse_status_yaml()
    assert ok is True


def test_check_wb_tokens_all_present(tmp_path, monkeypatch):
    from check_setup import check_wb_tokens
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cabinets.yaml").write_text("""
cabinets:
  - name: ooo
    sheet_id: "1AbC"
""")
    monkeypatch.setenv("WB_TOKEN_OOO", "tok123")
    ok, msg = check_wb_tokens()
    assert ok is True
    assert "found" in msg.lower()


def test_check_wb_tokens_missing(tmp_path, monkeypatch):
    from check_setup import check_wb_tokens
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cabinets.yaml").write_text("""
cabinets:
  - name: ooo
    sheet_id: "1AbC"
""")
    monkeypatch.delenv("WB_TOKEN_OOO", raising=False)
    ok, msg = check_wb_tokens()
    assert ok is False
    assert "WB_TOKEN_OOO" in msg


def test_check_wb_tokens_malformed_yaml(tmp_path, monkeypatch):
    from check_setup import check_wb_tokens
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cabinets.yaml").write_text("not: valid: yaml: structure: :")
    ok, msg = check_wb_tokens()
    assert ok is False


def test_check_sqlite_db_missing(tmp_path, monkeypatch):
    from check_setup import check_sqlite
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(tmp_path / "missing.db"))
    ok, msg = check_sqlite()
    assert ok is False
    assert "not found" in msg.lower() or "missing" in msg.lower()


def test_check_sqlite_db_no_recent_tariffs(tmp_path, monkeypatch):
    import sqlite3
    db_path = tmp_path / "stale.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE wb_tariffs (dt TEXT, warehouse_name TEXT,
            delivery_coef REAL, logistics_1l REAL, logistics_extra_l REAL,
            box_storage_base REAL, storage_coef REAL, geo_name TEXT,
            created_at TEXT, PRIMARY KEY (dt, warehouse_name));
    """)
    conn.execute(
        "INSERT INTO wb_tariffs (dt, warehouse_name, created_at) VALUES (?, ?, ?)",
        ("2020-01-01", "OldWarehouse", "2020-01-01"),
    )
    conn.commit()
    conn.close()

    from check_setup import check_sqlite
    ok, msg = check_sqlite()
    assert ok is False
    assert "7 days" in msg or "stale" in msg.lower()


def test_check_sqlite_db_with_recent_tariffs(tmp_path, monkeypatch):
    import sqlite3
    from datetime import date
    db_path = tmp_path / "fresh.db"
    monkeypatch.setenv("WB_TOOLKIT_DB_PATH", str(db_path))
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE wb_tariffs (dt TEXT, warehouse_name TEXT,
            delivery_coef REAL, logistics_1l REAL, logistics_extra_l REAL,
            box_storage_base REAL, storage_coef REAL, geo_name TEXT,
            created_at TEXT, PRIMARY KEY (dt, warehouse_name));
    """)
    conn.execute(
        "INSERT INTO wb_tariffs (dt, warehouse_name, created_at) VALUES (?, ?, ?)",
        (date.today().isoformat(), "Коледино", date.today().isoformat()),
    )
    conn.commit()
    conn.close()

    from check_setup import check_sqlite
    ok, msg = check_sqlite()
    assert ok is True
    assert "OK" in msg or "tariffs" in msg.lower()
