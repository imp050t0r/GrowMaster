from __future__ import annotations

import json
import math
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
INVENTORY_FILENAME = "growmaster-seed-inventory.json"
VALID_UNITS = {"g", "seeds", "pellets"}


def inventory_path() -> Path:
    configured = os.getenv("GROWMASTER_SEED_INVENTORY_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    root = Path(os.getenv("GROWMASTER_DATA_ROOT", "/data"))
    return root / INVENTORY_FILENAME


def _empty_inventory() -> dict:
    return {"schema_version": SCHEMA_VERSION, "next_id": 1, "lots": [], "transactions": []}


def load_inventory() -> dict:
    path = inventory_path()
    if not path.exists():
        return _empty_inventory()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Nepodprta različica Seed Inventory datoteke.")
    payload.setdefault("lots", [])
    payload.setdefault("transactions", [])
    payload.setdefault("next_id", 1)
    return payload


def save_inventory(payload: dict) -> None:
    path = inventory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def normalize_unit(unit: str) -> str:
    unit = unit.strip().lower()
    aliases = {"gram": "g", "grams": "g", "seed": "seeds", "seme": "seeds", "semena": "seeds", "pellet": "pellets", "pelet": "pellets", "peleti": "pellets"}
    unit = aliases.get(unit, unit)
    if unit not in VALID_UNITS:
        raise ValueError("Enota mora biti g, seeds ali pellets.")
    return unit


def convert_quantity(quantity: float, from_unit: str, to_unit: str, thousand_seed_weight_g: float | None) -> float:
    from_unit = normalize_unit(from_unit)
    to_unit = normalize_unit(to_unit)
    if from_unit == to_unit:
        return quantity
    if {from_unit, to_unit} <= {"seeds", "pellets"}:
        return quantity
    if not thousand_seed_weight_g or thousand_seed_weight_g <= 0:
        raise ValueError("Za pretvorbo med grami in številom semen je potreben TKW/TSW (g/1000 semen).")
    if from_unit == "g":
        count = quantity / thousand_seed_weight_g * 1000.0
    else:
        count = quantity
    if to_unit == "g":
        return count / 1000.0 * thousand_seed_weight_g
    return count


def create_lot(data: dict[str, Any]) -> dict:
    payload = load_inventory()
    unit = normalize_unit(str(data["unit"]))
    quantity = float(data["quantity"])
    if quantity < 0:
        raise ValueError("Zaloga ne more biti negativna.")
    lot = {
        "id": payload["next_id"],
        "crop": str(data["crop"]).strip(),
        "variety": str(data.get("variety") or "").strip() or None,
        "supplier": str(data.get("supplier") or "").strip() or None,
        "lot_number": str(data.get("lot_number") or "").strip() or None,
        "unit": unit,
        "quantity": round(quantity, 4),
        "package_size": float(data["package_size"]) if data.get("package_size") is not None else None,
        "thousand_seed_weight_g": float(data["thousand_seed_weight_g"]) if data.get("thousand_seed_weight_g") is not None else None,
        "germination_pct": float(data.get("germination_pct", 100.0)),
        "field_emergence_pct": float(data.get("field_emergence_pct", 100.0)),
        "purchase_date": data.get("purchase_date"),
        "expiry_date": data.get("expiry_date"),
        "notes": data.get("notes"),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    if not lot["crop"]:
        raise ValueError("Kultura je obvezna.")
    if not 0 < lot["germination_pct"] <= 100 or not 0 < lot["field_emergence_pct"] <= 100:
        raise ValueError("Kalivost in field emergence morata biti med 0 in 100 %.")
    payload["next_id"] += 1
    payload["lots"].append(lot)
    save_inventory(payload)
    return lot


def list_lots(crop: str | None = None, variety: str | None = None) -> list[dict]:
    lots = load_inventory()["lots"]
    if crop:
        lots = [lot for lot in lots if lot["crop"].casefold() == crop.casefold()]
    if variety:
        lots = [lot for lot in lots if (lot.get("variety") or "").casefold() == variety.casefold()]
    return lots


def find_lot(lot_id: int) -> tuple[dict, dict]:
    payload = load_inventory()
    for lot in payload["lots"]:
        if lot["id"] == lot_id:
            return payload, lot
    raise KeyError(lot_id)


def adjust_lot(lot_id: int, quantity: float, unit: str, reason: str, reference: str | None = None) -> dict:
    payload, lot = find_lot(lot_id)
    delta = convert_quantity(float(quantity), unit, lot["unit"], lot.get("thousand_seed_weight_g"))
    new_qty = lot["quantity"] + delta
    if new_qty < -1e-6:
        raise ValueError("Na zalogi ni dovolj semena za to operacijo.")
    lot["quantity"] = round(max(0.0, new_qty), 4)
    lot["updated_at"] = datetime.utcnow().isoformat() + "Z"
    payload["transactions"].append({
        "id": len(payload["transactions"]) + 1,
        "lot_id": lot_id,
        "quantity": float(quantity),
        "unit": normalize_unit(unit),
        "quantity_in_lot_unit": round(delta, 4),
        "reason": reason,
        "reference": reference,
        "created_at": datetime.utcnow().isoformat() + "Z",
    })
    save_inventory(payload)
    return lot


def requirement_from_target_plants(target_plants: int, germination_pct: float, field_emergence_pct: float, reserve_pct: float = 5.0) -> int:
    effective = (germination_pct / 100.0) * (field_emergence_pct / 100.0)
    if effective <= 0:
        raise ValueError("Kalivost in field emergence morata biti večja od 0.")
    return math.ceil(target_plants / effective * (1.0 + reserve_pct / 100.0))


def stock_summary(crop: str, variety: str | None = None, target_unit: str = "seeds") -> dict:
    target_unit = normalize_unit(target_unit)
    lots = list_lots(crop, variety)
    total = 0.0
    convertible = 0
    skipped = 0
    for lot in lots:
        try:
            total += convert_quantity(lot["quantity"], lot["unit"], target_unit, lot.get("thousand_seed_weight_g"))
            convertible += 1
        except ValueError:
            skipped += 1
    return {
        "crop": crop,
        "variety": variety,
        "unit": target_unit,
        "quantity": round(total, 2),
        "lot_count": len(lots),
        "convertible_lots": convertible,
        "unconvertible_lots": skipped,
    }


def purchase_recommendation(required_quantity: float, required_unit: str, available_quantity: float, package_size: float | None) -> dict:
    shortage = max(0.0, required_quantity - available_quantity)
    packages = math.ceil(shortage / package_size) if shortage > 0 and package_size and package_size > 0 else 0
    return {
        "required_quantity": round(required_quantity, 2),
        "unit": normalize_unit(required_unit),
        "available_quantity": round(available_quantity, 2),
        "shortage": round(shortage, 2),
        "package_size": package_size,
        "packages_to_order": packages,
        "order_quantity": round(packages * package_size, 2) if package_size else None,
        "status": "OK" if shortage <= 0 else "ORDER",
    }
