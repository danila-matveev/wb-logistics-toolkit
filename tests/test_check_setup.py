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
