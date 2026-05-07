"""Sheet 4: 'Детализация' — full reportDetailByPeriod dump."""
from __future__ import annotations
import re
from openpyxl.worksheet.worksheet import Worksheet
from audit.models.report_row import ReportRow

# openpyxl rejects control chars except \t \n \r
_ILLEGAL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _safe_value(val):
    """Sanitize value for openpyxl: strip illegal XML characters from strings."""
    if isinstance(val, str):
        return _ILLEGAL_CHARS_RE.sub("", val)
    return val


def write_detail(ws: Worksheet, rows: list[ReportRow]) -> None:
    """Write all raw fields from reportDetailByPeriod."""
    if not rows or not rows[0].raw:
        return
    columns = list(rows[0].raw.keys())
    for col, key in enumerate(columns, 1):
        ws.cell(1, col, key)
    for i, row in enumerate(rows, 2):
        if not row.raw:
            continue
        for col, key in enumerate(columns, 1):
            ws.cell(i, col, _safe_value(row.raw.get(key, "")))
