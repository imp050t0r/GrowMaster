from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.mix_recipes import BABY_LEAF_MIX_RECIPES, calculate_mix_seed_requirements
from app.seed_inventory_link import planting_consumption_status
from app.seed_inventory_service import (
    adjust_lot,
    create_lot,
    inventory_path,
    list_lots,
    load_inventory,
    purchase_recommendation,
    requirement_from_target_plants,
    stock_summary,
)

router = APIRouter()

class SeedLotCreate(BaseModel):
    crop: str
    variety: str | None = None
    supplier: str | None = None
    lot_number: str | None = None
    unit: str = Field(description="g, seeds ali pellets")
    quantity: float = Field(ge=0)
    package_size: float | None = Field(default=None, gt=0)
    thousand_seed_weight_g: float | None = Field(default=None, gt=0)
    germination_pct: float = Field(default=100, gt=0, le=100)
    field_emergence_pct: float = Field(default=100, gt=0, le=100)
    purchase_date: str | None = None
    expiry_date: str | None = None
    notes: str | None = None

class SeedAdjustment(BaseModel):
    quantity: float
    unit: str
    reason: str
    reference: str | None = None

@router.get("/api/seed-inventory")
def seed_inventory(crop: str | None = None, variety: str | None = None) -> dict:
    payload = load_inventory()
    lots = list_lots(crop, variety)
    return {"path": str(inventory_path()), "schema_version": payload.get("schema_version"), "lot_count": len(lots), "lots": lots}

@router.post("/api/seed-inventory/lots")
def add_seed_lot(body: SeedLotCreate) -> dict:
    try:
        lot = create_lot(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Semenska zaloga je dodana.", "lot": lot}

@router.post("/api/seed-inventory/lots/{lot_id}/adjust")
def adjust_seed_lot(lot_id: int, body: SeedAdjustment) -> dict:
    try:
        lot = adjust_lot(lot_id, body.quantity, body.unit, body.reason, body.reference)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Semenska serija ne obstaja.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Zaloga je posodobljena.", "lot": lot}

@router.get("/api/seed-inventory/summary")
def seed_inventory_summary(crop: str, variety: str | None = None, unit: str = Query(default="seeds")) -> dict:
    try:
        return stock_summary(crop, variety, unit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/api/seed-inventory/plant-requirement")
def plant_requirement(target_plants: int = Query(gt=0), germination_pct: float = Query(default=95, gt=0, le=100), field_emergence_pct: float = Query(default=90, gt=0, le=100), reserve_pct: float = Query(default=5, ge=0, le=100)) -> dict:
    required = requirement_from_target_plants(target_plants, germination_pct, field_emergence_pct, reserve_pct)
    return {"target_plants": target_plants, "germination_pct": germination_pct, "field_emergence_pct": field_emergence_pct, "reserve_pct": reserve_pct, "required_seeds": required}

@router.get("/api/seed-inventory/order-recommendation")
def seed_order_recommendation(required_quantity: float = Query(gt=0), required_unit: str = Query(default="seeds"), available_quantity: float = Query(default=0, ge=0), package_size: float | None = Query(default=None, gt=0)) -> dict:
    try:
        return purchase_recommendation(required_quantity, required_unit, available_quantity, package_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/api/seed-inventory/mix-recipes")
def mix_recipes() -> dict:
    return {"count": len(BABY_LEAF_MIX_RECIPES), "recipes": BABY_LEAF_MIX_RECIPES}

@router.get("/api/seed-inventory/mix-recipes/{recipe_id}/bed-requirement")
def mix_bed_requirement(
    recipe_id: str,
    width_m: float = Query(gt=0, le=100),
    length_m: float = Query(gt=0, le=1000),
    reserve_pct: float = Query(default=5, ge=0, le=100),
) -> dict:
    # Rates are supplied from the agronomic crop database as it is expanded.
    # Known professional rate for baby-leaf dandelion is included now; missing
    # component rates are deliberately reported instead of silently guessed.
    seed_rates = {"Baby leaf regrat": 0.65}
    try:
        result = calculate_mix_seed_requirements(recipe_id, width_m, length_m, seed_rates, reserve_pct)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receptura mešanice ne obstaja.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    for component in result["components"]:
        required = component.get("required_seed_g")
        if required is None:
            component["stock"] = {"status": "RATE_MISSING", "available_g": None, "shortage_g": None}
            continue
        summary = stock_summary(component["crop"], target_unit="g")
        available = summary["quantity"]
        component["stock"] = {
            "status": "OK" if available >= required else "ORDER",
            "available_g": available,
            "shortage_g": round(max(0.0, required - available), 2),
        }
    return result

@router.get("/api/seed-inventory/plantings/{planting_id}/consumption")
def planting_seed_consumption(planting_id: int) -> dict:
    record = planting_consumption_status(planting_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Za to setev še ni inventarnega obračuna.")
    return record

@router.get("/api/seed-inventory/planting-consumptions")
def planting_seed_consumptions(status: str | None = None, limit: int = Query(default=100, ge=1, le=1000)) -> dict:
    records = list(reversed(load_inventory().get("planting_consumptions", [])))
    if status:
        records = [item for item in records if item.get("status") == status]
    return {"count": min(len(records), limit), "records": records[:limit]}
