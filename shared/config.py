from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Cabinet:
    name: str
    wb_token: str
    sheet_id: str


@dataclass(frozen=True)
class WarehouseStatus:
    name: str
    fd: str
    available: bool
    redistribution_limit_per_day: int
    reason: str = ""
    note: str = ""


def load_cabinets(cabinets_path: str | Path = "cabinets.yaml") -> list[Cabinet]:
    path = Path(cabinets_path)
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data or "cabinets" not in data:
        raise ValueError(f"Invalid cabinets YAML in {path}: missing 'cabinets' key")
    result: list[Cabinet] = []
    for c in data["cabinets"]:
        name: str = c["name"]
        token_key = f"WB_TOKEN_{name.upper()}"
        token = os.environ.get(token_key)
        if not token:
            raise ValueError(
                f"Missing env var: {token_key} (required for cabinet '{name}')"
            )
        result.append(Cabinet(name=name, wb_token=token, sheet_id=c["sheet_id"]))
    return result


def get_cabinet(
    name: str, cabinets_path: str | Path = "cabinets.yaml"
) -> Cabinet:
    for cab in load_cabinets(cabinets_path):
        if cab.name == name:
            return cab
    raise ValueError(f"Cabinet '{name}' not found in {cabinets_path}")


def load_warehouse_statuses(
    warehouse_path: str | Path = "warehouse_status.yaml",
    available_only: bool = False,
) -> dict[str, WarehouseStatus]:
    path = Path(warehouse_path)
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data or "warehouses" not in data:
        raise ValueError(f"Invalid warehouse YAML in {path}: missing 'warehouses' key")
    result: dict[str, WarehouseStatus] = {}
    for w in data["warehouses"]:
        status = WarehouseStatus(
            name=w["name"],
            fd=w["fd"],
            available=bool(w.get("available", True)),
            redistribution_limit_per_day=int(
                w.get("redistribution_limit_per_day", 5000)
            ),
            reason=w.get("reason", ""),
            note=w.get("note", ""),
        )
        if available_only and not status.available:
            continue
        result[status.name] = status
    return result
