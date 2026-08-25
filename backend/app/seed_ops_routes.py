from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Crop, CropPlan, Planting, Supplier, SupplyItem
from app.seed_inventory_service import convert_quantity, list_lots, load_inventory
from app.seed_quantity import calculate_seed_quantity
from app.seeding_profiles import seeding_profile

router = APIRouter()
DEFAULT_FARM_ID = 1


def _plan_need(plan: CropPlan, reserve_pct: float) -> tuple[float, str] | None:
    profile = seeding_profile(plan.crop.name, plan.variety.name, plan.crop.family, plan.crop.category)
    rate = profile.get("seed_rate_g_m2")
    if rate is None:
        return None
    result = calculate_seed_quantity(float(rate), plan.bed.width_m, plan.bed.length_m, 1, reserve_pct)
    return float(result["total_grams_with_reserve"]), "g"


def _converted(lot: dict, target_unit: str, field: str = "quantity") -> float | None:
    value = lot.get(field)
    if value in (None, ""):
        return None
    try:
        return convert_quantity(float(value), lot["unit"], target_unit, lot.get("thousand_seed_weight_g"))
    except ValueError:
        return None


def reservation_snapshot(db: Session, start: date, end: date, reserve_pct: float = 5.0) -> dict:
    plans = list(db.scalars(
        select(CropPlan)
        .where(CropPlan.farm_id == DEFAULT_FARM_ID, CropPlan.status == "planned", CropPlan.sowing_date >= start, CropPlan.sowing_date <= end)
        .options(selectinload(CropPlan.bed), selectinload(CropPlan.crop), selectinload(CropPlan.variety))
        .order_by(CropPlan.sowing_date, CropPlan.id)
    ).all())
    grouped: dict[tuple[str, str, str], dict] = {}
    warnings: list[dict] = []
    for plan in plans:
        need = _plan_need(plan, reserve_pct)
        if need is None:
            warnings.append({"crop_plan_id": plan.id, "crop": plan.crop.name, "variety": plan.variety.name, "code": "missing_seed_rate"})
            continue
        quantity, unit = need
        key = (plan.crop.name, plan.variety.name, unit)
        row = grouped.setdefault(key, {"crop": plan.crop.name, "variety": plan.variety.name, "unit": unit, "reserved_quantity": 0.0, "plans": []})
        row["reserved_quantity"] += quantity
        row["plans"].append({"crop_plan_id": plan.id, "bed": plan.bed.name, "sowing_date": plan.sowing_date, "reserved_quantity": round(quantity, 2), "unit": unit})

    items: list[dict] = []
    for row in grouped.values():
        lots = list_lots(row["crop"], row["variety"])
        physical = sum(value for lot in lots if (value := _converted(lot, row["unit"])) is not None)
        packages = [value for lot in lots if (value := _converted(lot, row["unit"], "package_size")) is not None and value > 0]
        package_size = min(packages) if packages else None
        reserved = round(row["reserved_quantity"], 2)
        free = physical - reserved
        shortage = max(0.0, -free)
        package_count = math.ceil(shortage / package_size) if shortage and package_size else 0
        supplier_hint = next((lot.get("supplier") for lot in lots if lot.get("supplier")), None)
        status = "ORDER" if shortage > 0 else ("LOW_STOCK" if free <= reserved * 0.2 else "OK")
        items.append({**row, "reserved_quantity": reserved, "physical_quantity": round(physical, 2), "free_quantity": round(free, 2), "shortage": round(shortage, 2), "package_size": round(package_size, 2) if package_size else None, "packages_to_order": package_count, "order_quantity": round(package_count * package_size, 2) if package_count and package_size else None, "supplier_hint": supplier_hint, "status": status})
    items.sort(key=lambda item: ({"ORDER": 0, "LOW_STOCK": 1, "OK": 2}[item["status"]], item["crop"], item["variety"]))
    return {"planned_sowings": len(plans), "items": items, "warnings": warnings}


@router.get("/api/seed-inventory/reservations")
def reservations(start_date: date | None = Query(default=None), horizon_days: int = Query(default=56, ge=1, le=365), reserve_pct: float = Query(default=5.0, ge=0, le=100), db: Session = Depends(get_db)) -> dict:
    start = start_date or date.today()
    end = start + timedelta(days=horizon_days)
    snap = reservation_snapshot(db, start, end, reserve_pct)
    return {"start_date": start, "end_date": end, "horizon_days": horizon_days, "reserve_pct": reserve_pct, **snap, "summary": {"ok": sum(i["status"] == "OK" for i in snap["items"]), "low_stock": sum(i["status"] == "LOW_STOCK" for i in snap["items"]), "order": sum(i["status"] == "ORDER" for i in snap["items"]), "warnings": len(snap["warnings"])}}


@router.get("/api/seed-inventory/purchase-drafts")
def purchase_drafts(horizon_days: int = Query(default=56, ge=1, le=365), db: Session = Depends(get_db)) -> dict:
    snap = reservation_snapshot(db, date.today(), date.today() + timedelta(days=horizon_days))
    suppliers = {s.name.casefold(): s for s in db.scalars(select(Supplier).where(Supplier.farm_id == DEFAULT_FARM_ID)).all()}
    supply_items = {s.name.casefold(): s for s in db.scalars(select(SupplyItem).where(SupplyItem.farm_id == DEFAULT_FARM_ID)).all()}
    drafts = []
    for row in snap["items"]:
        if row["status"] != "ORDER":
            continue
        item_name = f"Seme – {row['crop']} {row['variety']}"
        supplier = suppliers.get((row.get("supplier_hint") or "").casefold())
        supply_item = supply_items.get(item_name.casefold())
        drafts.append({"crop": row["crop"], "variety": row["variety"], "shortage": row["shortage"], "unit": row["unit"], "package_size": row["package_size"], "packages_to_order": row["packages_to_order"], "order_quantity": row["order_quantity"], "supplier_hint": row.get("supplier_hint"), "supplier_id": supplier.id if supplier else None, "supply_item_id": supply_item.id if supply_item else None, "supply_item_name": item_name, "ready_for_purchase_order": bool(supplier and supply_item and row["order_quantity"]), "purchase_order_payload": {"supplier_id": supplier.id if supplier else None, "order_date": date.today(), "expected_date": None, "payment_method": "bank_transfer", "notes": f"GrowMaster Seed Forecast: {row['crop']} {row['variety']}", "items": [{"supply_item_id": supply_item.id if supply_item else None, "quantity": row["order_quantity"], "unit_price_eur": None}]}, "missing_setup": [name for missing, name in ((supplier is None, "supplier"), (supply_item is None, "supply_item"), (row["package_size"] is None, "package_size")) if missing]})
    return {"count": len(drafts), "drafts": drafts, "message": "Osnutek je povezan z obstoječim Purchase Order formatom; pred oddajo dopolni ceno."}


@router.get("/api/master-data/quality")
def master_data_quality(db: Session = Depends(get_db)) -> dict:
    crops = list(db.scalars(select(Crop).options(selectinload(Crop.varieties))).all())
    rows = []
    fields = ("seed_rate_g_m2", "seed_spacing_cm", "row_spacing_cm", "planting_method", "outdoor_months", "heat_tolerance", "cold_tolerance")
    bands = defaultdict(int)
    for crop in crops:
        for variety in crop.varieties:
            profile = seeding_profile(crop.name, variety.name, crop.family, crop.category)
            missing = [field for field in fields if getattr(variety, field, None) in (None, "")]
            if profile.get("jang_jp1", {}).get("roller") is None and profile.get("production_type") != "transplant":
                missing.append("jang_jp1_roller")
            if not list_lots(crop.name, variety.name):
                missing.append("inventory_lot")
            score = max(0, round(100 * (1 - len(missing) / (len(fields) + 2))))
            status = "complete" if score >= 85 else ("partial" if score >= 50 else "incomplete")
            bands[status] += 1
            rows.append({"crop": crop.name, "variety": variety.name, "score": score, "status": status, "missing": missing})
    rows.sort(key=lambda row: (row["score"], row["crop"], row["variety"]))
    return {"count": len(rows), "summary": dict(bands), "items": rows}


@router.get("/api/agronomy/learning")
def agronomy_learning(min_samples: int = Query(default=2, ge=1, le=20), db: Session = Depends(get_db)) -> dict:
    plantings = list(db.scalars(select(Planting).where(Planting.farm_id == DEFAULT_FARM_ID).options(selectinload(Planting.crop), selectinload(Planting.variety), selectinload(Planting.bed), selectinload(Planting.harvests))).all())
    consumptions = {int(item["planting_id"]): item for item in load_inventory().get("planting_consumptions", []) if item.get("planting_id") is not None}
    grouped = defaultdict(list)
    for planting in plantings:
        if not planting.harvests or not planting.bed.area_m2:
            continue
        first_harvest = min(h.harvest_date for h in planting.harvests)
        consumption = consumptions.get(planting.id)
        rate = None
        if consumption and consumption.get("status") == "consumed" and consumption.get("required_unit") == "g":
            rate = float(consumption.get("required_quantity", 0)) / 1.05 / planting.bed.area_m2
        grouped[(planting.crop.name, planting.variety.name)].append({"planting_id": planting.id, "actual_dtm": (first_harvest - planting.sowing_date).days, "seed_rate_g_m2": rate, "yield_kg_m2": sum(h.quantity_kg for h in planting.harvests) / planting.bed.area_m2})
    suggestions = []
    for (crop_name, variety_name), samples in grouped.items():
        if len(samples) < min_samples:
            continue
        planting = next(p for p in plantings if p.crop.name == crop_name and p.variety.name == variety_name)
        dtms = [s["actual_dtm"] for s in samples if s["actual_dtm"] > 0]
        rates = [s["seed_rate_g_m2"] for s in samples if s["seed_rate_g_m2"] is not None]
        yields = [s["yield_kg_m2"] for s in samples]
        observed_dtm = round(sum(dtms) / len(dtms)) if dtms else None
        observed_rate = round(sum(rates) / len(rates), 3) if rates else None
        current_rate = seeding_profile(crop_name, variety_name, planting.crop.family, planting.crop.category).get("seed_rate_g_m2")
        dtm_delta = observed_dtm - planting.variety.days_to_harvest if observed_dtm is not None else None
        rate_delta = (observed_rate / current_rate - 1) * 100 if observed_rate is not None and current_rate else None
        suggestions.append({"crop": crop_name, "variety": variety_name, "samples": len(samples), "confidence": "high" if len(samples) >= 5 else ("medium" if len(samples) >= 3 else "low"), "current_days_to_harvest": planting.variety.days_to_harvest, "observed_days_to_harvest": observed_dtm, "dtm_delta_days": dtm_delta, "current_seed_rate_g_m2": current_rate, "observed_seed_rate_g_m2": observed_rate, "seed_rate_delta_pct": round(rate_delta, 1) if rate_delta is not None else None, "observed_yield_kg_m2": round(sum(yields) / len(yields), 2), "recommend_seed_rate_update": bool(rate_delta is not None and abs(rate_delta) >= 10 and len(rates) >= min_samples), "recommend_dtm_review": bool(dtm_delta is not None and abs(dtm_delta) >= 5)})
    suggestions.sort(key=lambda item: (-item["samples"], item["crop"], item["variety"]))
    return {"min_samples": min_samples, "count": len(suggestions), "suggestions": suggestions, "principle": "Predlogi temeljijo na dejanskih rezultatih; master podatkov ne prepisujemo tiho."}
