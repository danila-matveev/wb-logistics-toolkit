"""Output writers for localization phases.

Two implementations behind a single `Writer` Protocol:
- `SheetsWriter` writes to Google Sheets (via gspread).
- `ExcelWriter` writes to a local `.xlsx` file (via openpyxl).

`make_writer()` is the factory: it picks one based on cabinet config + env.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol

from openpyxl import Workbook


class Writer(Protocol):
    """Sink for tabular sheet data. Implementations decide where rows go."""

    def write_sheet(self, name: str, rows: list[list[Any]]) -> None:
        """Write `rows` to a sheet identified by `name` (idempotent / replace)."""
        ...

    def finalize(self) -> str | None:
        """Flush pending writes. Returns local path for Excel, None for Sheets."""
        ...


class ExcelWriter:
    """openpyxl-backed writer. Buffers sheets in memory, saves on `finalize()`."""

    def __init__(self, output_path: str) -> None:
        self._output_path = output_path
        self._wb = Workbook()
        # Workbook starts with a default "Sheet" — we'll remove it lazily once
        # the first real sheet arrives. If finalize() runs without any writes
        # at all, leave the default in place so the file is at least valid.
        self._default_removed = False

    def write_sheet(self, name: str, rows: list[list[Any]]) -> None:
        if not self._default_removed:
            default = self._wb.active
            if default is not None and default.title == "Sheet":
                self._wb.remove(default)
            self._default_removed = True
        ws = self._wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)

    def finalize(self) -> str:
        Path(self._output_path).parent.mkdir(parents=True, exist_ok=True)
        self._wb.save(self._output_path)
        return self._output_path


class SheetsWriter:
    """gspread-backed writer. Each `write_sheet` call upserts a worksheet."""

    def __init__(self, spreadsheet: Any) -> None:
        # `Any` to avoid an unconditional gspread import at module load time;
        # the runner provides a real `gspread.Spreadsheet`.
        self._spreadsheet = spreadsheet

    def write_sheet(self, name: str, rows: list[list[Any]]) -> None:
        from shared.sheets_client import clear_and_write, get_or_create_worksheet
        ws = get_or_create_worksheet(self._spreadsheet, name)
        clear_and_write(ws, rows)

    def finalize(self) -> None:
        return None


def _open_spreadsheet(sheet_id: str) -> Any:
    """Open a gspread spreadsheet by id. Indirected so tests can patch it."""
    from shared.sheets_client import get_client
    gc = get_client()
    return gc.open_by_key(sheet_id)


def make_writer(
    *,
    sheet_id: str | None,
    excel_path: str,
    force_excel: bool,
) -> Writer:
    """Pick a writer per spec §1.2.

    Excel-fallback is the default: SheetsWriter is only chosen when ALL hold —
    `sheet_id` is set and not the YAML placeholder, `--no-sheets` was not
    passed, and `GOOGLE_CREDENTIALS_PATH` points to an existing file.
    """
    if force_excel:
        return ExcelWriter(excel_path)

    sheet_id_clean = (sheet_id or "").strip()
    if not sheet_id_clean or sheet_id_clean == "YOUR_SHEET_ID_HERE":
        return ExcelWriter(excel_path)

    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "").strip()
    if not creds_path or not Path(creds_path).exists():
        return ExcelWriter(excel_path)

    spreadsheet = _open_spreadsheet(sheet_id_clean)
    return SheetsWriter(spreadsheet)
