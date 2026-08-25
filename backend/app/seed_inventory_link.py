from __future__ import annotations

import math
from datetime import datetime

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models import Bed, Crop, Planting, Variety
from app.seed_inventory_service import (
    convert_quantity,
    load_inventory,
    save_inventory,
)
from app.seeding_profiles import seeding_profile


DEFAULT_RESERVE_PCT = 5.0
_SESSION_KEY = "growmaster_new_planting_ids"


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _matching_lots(payload: dict, crop: str, variety: str | None) -> list[dict]:
    exact = []
    generic = []
    for lot in payload.get("lots", []):
        if str(lot.get("crop", "")).casefold() != crop.casefold():
            continue
        lot_variety = (lot.get("variety") or "").strip()
        if variety and lot_variety.casefold() == variety.casefold():
            exact.append(lot)
        elif not lot_variety:
            generic.append(lot)
    # FIFO by purchase date/creation, exact variety before generic crop lots.
    key = lambda lot: (lot.get("purchase_date") or "9999-99-99", lot.get("created_at") or "", lot.get("id", 0))
    return sorted(exact, key=key) + sorted(generic, key=key)


def _already_processed(payload: dict, planting_id: int) -> dict | None:
    for record in payload.get("planting_consumptions", []):
        if record.get("planting_id") == planting_id:
            return record
    return None


def _requirement_for_planting(bed: Bed, crop: Crop, variety: Variety) -> dict:
    profile = seeding_profile(crop.name, variety.name, crop.family, crop.category)
    area_m2 = bed.area_m2
    seed_rate = profile.get("seed_rate_g_m2")
    if seed_rate is None:
        seed_rate = variety.seed_rate_g_m2

    if seed_rate is not None and float(seed_rate) > 0:
        base_g = area_m2 * float(seed_rate)
        total_g = base_g * (1.0 + DEFAULT_RESERVE_PCT / 100.0)
        return {
            "calculable": True,
            "quantity": round(total_g, 4),
            "unit": "g",
            "basis": "seed_rate_g_m2",
            "seed_rate_g_m2": float(seed_rate),
            "area_m2": area_m2,
            "reserve_pct": DEFAULT_RESERVE_PCT,
        }

    spacing = variety.seed_spacing_cm
    row_spacing = variety.row_spacing_cm
    if spacing and row_spacing and spacing > 0 and row_spacing > 0:
        positions = area_m2 / ((float(spacing) / 100.0) * (float(row_spacing) / 100.0))
        quantity = math.ceil(positions * (1.0 + DEFAULT_RESERVE_PCT / 100.0))
        return {
            "calculable": True,
            "quantity": quantity,
            "unit": "seeds",
            "basis": "seed_and_row_spacing",
            "seed_spacing_cm": float(spacing),
            "row_spacing_cm": float(row_spacing),
            "area_m2": area_m2,
            "reserve_pct": DEFAULT_RESERVE_PCT,
        }

    return {
        "calculable": False,
        "quantity": None,
        "unit": None,
        "basis": None,
        "area_m2": area_m2,
        "reserve_pct": DEFAULT_RESERVE_PCT,
        "message": "Za to sorto ni dovolj podatkov za avtomatski obračun semena.",
    }


def consume_for_planting(session: Session, planting_id: int) -> dict:
    payload = load_inventory()
    payload.setdefault("planting_consumptions", [])
    existing = _already_processed(payload, planting_id)
    if existing:
        return existing

    planting = session.get(Planting, planting_id)
    if planting is None:
        raise ValueError("Planting ne obstaja.")
    bed = session.get(Bed, planting.bed_id)
    crop = session.get(Crop, planting.crop_id)
    variety = session.get(Variety, planting.variety_id)
    if bed is None or crop is None or variety is None:
        raise ValueError("Planting nima veljavne gredice, kulture ali sorte.")

    requirement = _requirement_for_planting(bed, crop, variety)
    record = {
        "planting_id": planting.id,
        "bed_id": bed.id,
        "bed": bed.name,
        "crop": crop.name,
        "variety": variety.name,
        "requirement": requirement,
        "status": "not_calculable",
        "allocations": [],
        "created_at": _now(),
    }
    if not requirement["calculable"]:
        payload["planting_consumptions"].append(record)
        save_inventory(payload)
        return record

    required = float(requirement["quantity"])
    unit = str(requirement["unit"])
    remaining = required
    candidates = _matching_lots(payload, crop.name, variety.name)
    allocations: list[dict] = []

    for lot in candidates:
        if remaining <= 1e-6:
            break
        try:
            available_in_required_unit = convert_quantity(
                float(lot.get("quantity", 0.0)),
                str(lot.get("unit")),
                unit,
                lot.get("thousand_seed_weight_g"),
            )
        except ValueError:
            continue
        if available_in_required_unit <= 0:
            continue
        take_required_unit = min(remaining, available_in_required_unit)
        take_lot_unit = convert_quantity(
            take_required_unit,
            unit,
            str(lot.get("unit")),
            lot.get("thousand_seed_weight_g"),
        )
        allocations.append({
            "lot_id": lot["id"],
            "quantity": round(take_required_unit, 4),
            "unit": unit,
            "quantity_in_lot_unit": round(take_lot_unit, 4),
            "lot_unit": lot["unit"],
        })
        remaining -= take_required_unit

    if remaining > 1e-6:
        record["status"] = "insufficient_stock"
        record["shortage"] = round(remaining, 4)
        record["unit"] = unit
        record["allocations"] = allocations
        record["message"] = "Setev je evidentirana, vendar zaloga ni bila zmanjšana, ker ni dovolj pretvorljivega semena."
        payload["planting_consumptions"].append(record)
        save_inventory(payload)
        return record

    # Apply all allocations only after we know the full requirement can be covered.
    lots_by_id = {lot["id"]: lot for lot in payload.get("lots", [])}
    for allocation in allocations:
        lot = lots_by_id[allocation["lot_id"]]
        lot["quantity"] = round(max(0.0, float(lot["quantity"]) - allocation["quantity_in_lot_unit"]), 4)
        lot["updated_at"] = _now()
        payload.setdefault("transactions", []).append({
            "id": len(payload["transactions"]) + 1,
            "lot_id": lot["id"],
            "quantity": -allocation["quantity"],
            "unit": unit,
            "quantity_in_lot_unit": -allocation["quantity_in_lot_unit"],
            "reason": "automatic planting consumption",
            "reference": f"planting:{planting.id}",
            "created_at": _now(),
        })

    record["status"] = "consumed"
    record["allocations"] = allocations
    record["consumed_quantity"] = round(required, 4)
    record["unit"] = unit
    record["message"] = "Seme je bilo avtomatsko odšteto iz Seed Inventory."
    payload["planting_consumptions"].append(record)
    save_inventory(payload)
    return record


def planting_consumption_status(planting_id: int) -> dict | None:
    payload = load_inventory()
    return _already_processed(payload, planting_id)


def register_seed_inventory_hooks() -> None:
    if getattr(register_seed_inventory_hooks, "_registered", False):
        return

    @event.listens_for(Session, "before_flush")
    def _capture_new_plantings(session: Session, _flush_context, _instances) -> None:
        new_objects = [obj for obj in session.new if isinstance(obj, Planting)]
        if new_objects:
            session.info.setdefault(_SESSION_KEY, []).extend(new_objects)

    @event.listens_for(Session, "after_flush_postexec")
    def _consume_seed_after_flush(session: Session, _flush_context) -> None:
        objects = session.info.pop(_SESSION_KEY, [])
        for planting in objects:
            if planting.id is None:
                continue
            # Inventory failure must not corrupt the PostgreSQL planting transaction.
            try:
                consume_for_planting(session, int(planting.id))
            except Exception as exc:  # recorded for diagnosis; planting itself remains valid
                payload = load_inventory()
                payload.setdefault("planting_consumptions", []).append({
                    "planting_id": int(planting.id),
                    "status": "error",
                    "message": str(exc),
                    "created_at": _now(),
                })
                save_inventory(payload)

    register_seed_inventory_hooks._registered = True
