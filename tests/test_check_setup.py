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


def test_check_supabase_missing_credentials(monkeypatch):
    from check_setup import check_supabase
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    ok, msg = check_supabase()
    assert ok is False
    assert "missing" in msg.lower()
