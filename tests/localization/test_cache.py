# tests/localization/test_cache.py
import json
import os
import time
import warnings
from pathlib import Path

import pytest

from localization.data.cache import load_cache, save_cache


def test_save_creates_file(tmp_path):
    save_cache("testcab", {"x": 1, "y": [2, 3]}, cache_dir=tmp_path)
    cache_file = tmp_path / "testcab_latest.json"
    assert cache_file.exists()
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert data == {"x": 1, "y": [2, 3]}


def test_load_returns_data(tmp_path):
    save_cache("testcab", {"foo": "bar"}, cache_dir=tmp_path)
    result = load_cache("testcab", cache_dir=tmp_path)
    assert result == {"foo": "bar"}


def test_load_returns_none_if_missing(tmp_path):
    result = load_cache("notexist", cache_dir=tmp_path)
    assert result is None


def test_load_stale_emits_warning(tmp_path):
    save_cache("testcab", {"x": 1}, cache_dir=tmp_path)
    cache_file = tmp_path / "testcab_latest.json"
    old_mtime = time.time() - 25 * 3600  # 25 hours ago
    os.utime(cache_file, (old_mtime, old_mtime))
    with pytest.warns(RuntimeWarning, match="stale"):
        result = load_cache("testcab", cache_dir=tmp_path)
    assert result == {"x": 1}  # still returns data despite stale


def test_load_fresh_no_warning(tmp_path):
    save_cache("testcab", {"x": 1}, cache_dir=tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = load_cache("testcab", cache_dir=tmp_path)
    assert result == {"x": 1}


def test_save_overwrites(tmp_path):
    save_cache("testcab", {"v": 1}, cache_dir=tmp_path)
    save_cache("testcab", {"v": 2}, cache_dir=tmp_path)
    result = load_cache("testcab", cache_dir=tmp_path)
    assert result["v"] == 2


def test_multiple_cabinets(tmp_path):
    save_cache("cab1", {"n": 1}, cache_dir=tmp_path)
    save_cache("cab2", {"n": 2}, cache_dir=tmp_path)
    assert load_cache("cab1", cache_dir=tmp_path)["n"] == 1
    assert load_cache("cab2", cache_dir=tmp_path)["n"] == 2
