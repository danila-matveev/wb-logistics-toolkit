# shared/db.py
"""Local SQLite storage for wb-logistics-toolkit.

Replaces the prior Supabase-based storage. One writer (cron tariff collector),
N readers (audit/run_audit). WAL mode keeps readers unblocked during writes.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

_DEFAULT_PATH = "data/wb_toolkit.db"

_DDL = """
CREATE TABLE IF NOT EXISTS wb_tariffs (
    dt                TEXT NOT NULL,
    warehouse_name    TEXT NOT NULL,
    delivery_coef     REAL,
    logistics_1l      REAL,
    logistics_extra_l REAL,
    box_storage_base  REAL,
    storage_coef      REAL,
    geo_name          TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (dt, warehouse_name)
);
"""

_conn: sqlite3.Connection | None = None
_conn_lock = threading.Lock()


def _resolve_path() -> Path:
    raw = os.environ.get("WB_TOOLKIT_DB_PATH") or _DEFAULT_PATH
    return Path(raw)


def get_connection() -> sqlite3.Connection:
    """Return a process-wide SQLite connection, initialising WAL + schema once.

    Path is taken from `WB_TOOLKIT_DB_PATH` env var, defaulting to
    `data/wb_toolkit.db` relative to the current working directory.
    """
    global _conn
    if _conn is not None:
        return _conn
    with _conn_lock:
        if _conn is not None:
            return _conn
        path = _resolve_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_DDL)
        conn.commit()
        _conn = conn
    return _conn


def _reset_for_tests() -> None:
    """Drop the cached connection. ONLY for tests."""
    global _conn
    with _conn_lock:
        if _conn is not None:
            _conn.close()
        _conn = None
