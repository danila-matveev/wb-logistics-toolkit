from __future__ import annotations
from dataclasses import dataclass
from datetime import date

FIXED_RATE_TYPES = frozenset({
    "От клиента при отмене",
    "От клиента при возврате",
})

FORWARD_DELIVERY_TYPES = frozenset({
    "К клиенту при продаже",
    "К клиенту при отмене",
})


@dataclass
class ReportRow:
    """One row from reportDetailByPeriod v5."""
    realizationreport_id: int
    nm_id: int
    office_name: str
    supplier_oper_name: str
    bonus_type_name: str
    delivery_rub: float
    dlv_prc: float
    fix_tariff_date_from: date | None
    fix_tariff_date_to: date | None
    order_dt: date | None
    shk_id: int
    srid: str
    gi_id: int
    gi_box_type_name: str
    storage_fee: float
    penalty: float
    deduction: float
    rebill_logistic_cost: float
    ppvz_for_pay: float
    ppvz_supplier_name: str
    retail_amount: float
    date_from: str
    date_to: str
    doc_type_name: str
    acceptance: float
    raw: dict | None = None

    @property
    def is_logistics(self) -> bool:
        return self.supplier_oper_name == "Логистика"

    @property
    def is_fixed_rate(self) -> bool:
        return self.bonus_type_name in FIXED_RATE_TYPES

    @property
    def is_forward_delivery(self) -> bool:
        """Only forward deliveries are auditable for overpayment."""
        return self.bonus_type_name in FORWARD_DELIVERY_TYPES

    @classmethod
    def from_api(cls, d: dict) -> "ReportRow":
        return cls(
            realizationreport_id=d.get("realizationreport_id", 0),
            nm_id=d.get("nm_id", 0),
            office_name=d.get("office_name", ""),
            supplier_oper_name=d.get("supplier_oper_name", ""),
            bonus_type_name=d.get("bonus_type_name", ""),
            delivery_rub=d.get("delivery_rub", 0.0),
            dlv_prc=d.get("dlv_prc", 0.0),
            fix_tariff_date_from=_parse_date(d.get("fix_tariff_date_from")),
            fix_tariff_date_to=_parse_date(d.get("fix_tariff_date_to")),
            order_dt=_parse_date(d.get("order_dt")),
            shk_id=d.get("shk_id", 0),
            srid=d.get("srid", ""),
            gi_id=d.get("gi_id", 0),
            gi_box_type_name=d.get("gi_box_type_name", ""),
            storage_fee=d.get("storage_fee", 0.0),
            penalty=d.get("penalty", 0.0),
            deduction=d.get("deduction", 0.0),
            rebill_logistic_cost=d.get("rebill_logistic_cost", 0.0),
            ppvz_for_pay=d.get("ppvz_for_pay", 0.0),
            ppvz_supplier_name=d.get("ppvz_supplier_name", ""),
            retail_amount=d.get("retail_amount", 0.0),
            date_from=d.get("date_from", ""),
            date_to=d.get("date_to", ""),
            doc_type_name=d.get("doc_type_name", ""),
            acceptance=d.get("acceptance", 0.0),
            raw=d,
        )


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    s = val[:10]
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None
