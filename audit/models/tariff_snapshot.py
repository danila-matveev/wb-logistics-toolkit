from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TariffSnapshot:
    """Warehouse tariff snapshot from /api/v1/tariffs/box."""
    warehouse_name: str
    box_delivery_base: float
    box_delivery_liter: float
    delivery_coef_pct: int
    box_storage_base: float
    box_storage_liter: float
    storage_coef_pct: int
    geo_name: str = ""

    @classmethod
    def from_api(cls, d: dict) -> "TariffSnapshot":
        return cls(
            warehouse_name=d.get("warehouseName", ""),
            box_delivery_base=_parse_ru_decimal(d.get("boxDeliveryBase", "0")),
            box_delivery_liter=_parse_ru_decimal(d.get("boxDeliveryLiter", "0")),
            delivery_coef_pct=int(_parse_ru_decimal(d.get("boxDeliveryCoefExpr", "0"))),
            box_storage_base=_parse_ru_decimal(d.get("boxStorageBase", "0")),
            box_storage_liter=_parse_ru_decimal(d.get("boxStorageLiter", "0")),
            storage_coef_pct=int(_parse_ru_decimal(d.get("boxStorageCoefExpr", "0"))),
            geo_name=d.get("geoName", ""),
        )


def _parse_ru_decimal(val: str) -> float:
    """Parse Russian decimal: '89,7' → 89.7, '-' → 0.0, '1 046' → 1046.0"""
    if not val or val == "-":
        return 0.0
    return float(val.replace(",", ".").replace(" ", "").replace("\xa0", ""))
