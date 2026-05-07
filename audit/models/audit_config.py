from __future__ import annotations
from dataclasses import dataclass
from datetime import date


@dataclass
class AuditConfig:
    """Input parameters for the audit."""
    api_key: str
    date_from: date
    date_to: date
    ktr: float = 1.0
    cabinet: str = ""
