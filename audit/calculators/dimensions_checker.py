from __future__ import annotations
from dataclasses import dataclass


@dataclass
class DimensionResult:
    nm_id: int
    card_volume: float
    wb_volume: float
    pct_diff: float
    flagged: bool


def check_dimensions(
    card_dims: dict[int, float],
    wb_volumes: dict[int, float],
    threshold_pct: float = 10.0,
) -> dict[int, DimensionResult]:
    """Compare card dimensions vs WB measured volume. Flag if difference > threshold."""
    results = {}
    for nm_id, card_vol in card_dims.items():
        wb_vol = wb_volumes.get(nm_id)
        if wb_vol is None or card_vol == 0:
            continue
        pct = abs(wb_vol - card_vol) / card_vol * 100
        results[nm_id] = DimensionResult(
            nm_id=nm_id,
            card_volume=card_vol,
            wb_volume=wb_vol,
            pct_diff=round(pct, 2),
            flagged=pct > threshold_pct,
        )
    return results
