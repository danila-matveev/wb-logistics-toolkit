"""Standalone gspread helpers — no Wookiee dependencies."""
from __future__ import annotations

import json
import os
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def get_client(credentials_path: str | None = None) -> gspread.Client:
    """Build authenticated gspread Client.

    Args:
        credentials_path: Path to service account JSON file. Falls back to
            GOOGLE_CREDENTIALS_PATH env var if None.
    """
    path = credentials_path or os.environ.get("GOOGLE_CREDENTIALS_PATH", "")
    if not path:
        raise ValueError(
            "No Google credentials. Set GOOGLE_CREDENTIALS_PATH in .env "
            "or pass credentials_path=."
        )
    with open(path, encoding="utf-8") as f:
        info = json.load(f)
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    return gspread.authorize(creds)


def get_or_create_worksheet(
    spreadsheet: gspread.Spreadsheet,
    title: str,
    rows: int = 2000,
    cols: int = 30,
) -> gspread.Worksheet:
    """Get existing worksheet by title or create it."""
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


def clear_and_write(ws: gspread.Worksheet, data: list[list[Any]]) -> None:
    """Clear worksheet and write rows starting at A1."""
    ws.clear()
    if data:
        ws.update(range_name="A1", values=data)


def to_number(value: Any) -> float | str:
    """Convert value to float if possible, else return as string."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value) if value is not None else ""
