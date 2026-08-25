from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Crop, CropPlan, Harvest, Planting, Supplier, SupplyItem
from app.seed_inventory_service import convert_quantity, list_lots, load_inventory
from app.seed_quantity import calculate_seed_quantity
from app.seeding_profiles import load_seeding_data, save_inventory if False else seeding_data_path, seeding_profile


router = APIRouter()
DEFAULT_FARM_ID = 1


def _plan_need(plan: CropPlan, reserve_pct: float) -> dict | None:
    profile = seeding_profile(
        plan.crop.name,
        plan.variety.name,
        plan.crop.family,
        plan.crop.category,
    )
    seed_rate = profile.get("seed_rate_g_m2")
    if seed_rate is None:
        return None
    quantity = calculate_seed_quantity(
        seed_rate_g_m2=float(seed_rate),
        bed_width_m=plan.bed.width_m,
        bed_length_m=plan.bed.length_m,
        bed_count=1,
        reserve_pct=reserve_pct,
    )
    return {
        "quantity": float(quantity["total_grams_with_reserve"]),
        "unit": "g",
        "seed_rate_g_m2": float(seed_rate),
    }


def _lot_available(lot: dict, unit: str) -> float | None:
    try:
        return convert_quantity(
            float(lot.get("quantity", 0)),
            lot["unit"],
            unit,
            lot.get("thousand_seed_weight_g"),
        )
    except ValueError:
        return None


def _supplier_hint(lots: list[dict]) -> str | None:
    for lot in lots:
        if lot.get("supplier"):
            return str(lot["supplier"])
    return None


def _package_size(lots: list[dict], unit: str) -> float | None:
    candidates: list[float] = []
    for lot in lots:
        size = lot.get("package_size")
        if not size:
            continue
        try:
            candidates.append(
                convert_quantity(
                    float(size),
                    lot["unit"],
                    unit,
                    lot.get("thousand_seed_weight_g"),
                )
            )
        except ValueError:
            continue
    return min(candidates) if candidates else None


def _reservation_snapshot(
    db: Session,
    start: date,
    end: date,
    reserve_pct: float,
) -> dict:
    plans = list(
        db.scalars(
            select(CropPlan)
            .where(
                CropPlan.farm_id == DEFAULT_FARM_ID,
                CropPlan.status == "planned",
                CropPlan.sowing_date >= start,
                CropPlan.sowing_date <= end,
            )
            .options(
                selectinload(CropPlan.bed),
                selectinload(CropPlan.crop),
                selectinload(CropPlan.variety),
            )
            .order_by(CropPlan.sowing_date, CropPlan.id)
        ).all()
    )
    grouped: dict[tuple[str, str, str], dict] = {}
    warnings: list[dict] = []
    for plan in plans:
        need = _plan_need(plan, reserve_pct)
        if need is None:
            warnings.append({
                "crop_plan_id": plan.id,
                "crop": plan.crop.name,
                "variety": plan.variety.name,
                "code": "missing_seed_rate",
                "message": "Za plan ni določene zanesljive setvene norme.",
            })
            continue
        key = (plan.crop.name, plan.variety.name, need["unit"])
        row = grouped.setdefault(key, {
            "crop": plan.crop.name,
            "variety": plan.variety.name,
            "unit": need["unit"],
            "reserved_quantity": 0.0,
            "plans": [],
        })
        row["reserved_quantity"] += need["quantity"]
        row["plans"].append({
            "crop_plan_id": plan.id,
            "bed": plan.bed.name,
            "sowing_date": plan.sowing_date,
            "reserved_quantity": round(need["quantity"], 2),
            "unit": need["unit"],
        })

    items: list[dict] = []
    for row in grouped.values():
        lots = list_lots(row["crop"], row["variety"])
        physical = sum(
            value for lot in lots
            if (value := _lot_available(lot, row["unit"])) is not None
        )
        reserved = round(row["reserved_quantity"], 2)
        free = physical - reserved
        pkg = _package_size(lots, row["unit"])
        shortage = max(0.0, -free)
        packages = math.ceil(shortage / pkg) if shortage > 0 and pkg else 0
        items.append({
            **row,
            "reserved_quantity": reserved,
            "physical_quantity": round(physical, 2),
            "free_quantity": round(free, 2),
            "shortage": round(shortage, 2),
            "package_size": round(pkg, 2) if pkg else None,
            "packages_to_order": packages,
            "order_quantity": round(packages * pkg, 2) if packages and pkg else None,
            "supplier_hint": _supplier_hint(lots),
            "status": "ORDER" if shortage > 0 else ("LOW_STOCK" if free <= reserved * 0.2 else "OK"),
        })
    items.sort(key=lambda item: ({"ORDER": 0, "LOW_STOCK": 1, "OK": 2}[item["status"]], item["crop"], item["variety"]))
    return {"items": items, "warnings": warnings, "planned_sowings": len(plans)}


@router.get("/api/seed-inventory/reservations")
def seed_reservations(
    start_date: date | None = Query(default=None),
    horizon_days: int = Query(default=56, ge=1, le=365),
    reserve_pct: float = Query(default=5.0, ge=0, le=100),
    db: Session = Depends(get_db),
) -> dict:
    start = start_date or date.today()
    end = start + timedelta(days=horizon_days)
    snapshot = _reservation_snapshot(db, start, end, reserve_pct)
    return {
        "start_date": start,
        "end_date": end,
        "horizon_days": horizon_days,
        "reserve_pct": reserve_pct,
        **snapshot,
        "summary": {
            "ok": sum(1 for item in snapshot["items"] if item["status"] == "OK"),
            "low_stock": sum(1 for item in snapshot["items"] if item["status"] == "LOW_STOCK"),
            "order": sum(1 for item in snapshot["items"] if item["status"] == "ORDER"),
            "warnings": len(snapshot["warnings"]),
        },
    }


@router.get("/api/seed-inventory/purchase-drafts")
def seed_purchase_drafts(
    horizon_days: int = Query(default=56, ge=1, le=365),
    reserve_pct: float = Query(default=5.0, ge=0, le=100),
    db: Session = Depends(get_db),
) -> dict:
    start = date.today()
    snapshot = _reservation_snapshot(db, start, start + timedelta(days=horizon_days), reserve_pct)
    suppliers = list(db.scalars(select(Supplier).where(Supplier.farm_id == DEFAULT_FARM_ID)).all())
    supply_items = list(db.scalars(select(SupplyItem).where(SupplyItem.farm_id == DEFAULT_FARM_ID)).all())
    supplier_by_name = {supplier.name.casefold(): supplier for supplier in suppliers}
    item_by_name = {item.name.casefold(): item for item in supply_items}

    drafts: list[dict] = []
    for item in snapshot["items"]:
        if item["status"] != "ORDER":
            continue
        inventory_name = f"Seme – {item['crop']} {item['variety']}"
        supplier = supplier_by_name.get((item.get("supplier_hint") or "").casefold())
        supply_item = item_by_name.get(inventory_name.casefold())
        drafts.append({
            "crop": item["crop"],
            "variety": item["variety"],
            "shortage": item["shortage"],
            "unit": item["unit"],
            "package_size": item["package_size"],
            "packages_to_order": item["packages_to_order"],
            "order_quantity": item["order_quantity"],
            "supplier_hint": item.get("supplier_hint"),
            "supplier_id": supplier.id if supplier else None,
            "supply_item_id": supply_item.id if supply_item else None,
            "supply_item_name": inventory_name,
            "ready_for_purchase_order": bool(supplier and supply_item and item["order_quantity"]),
            "purchase_order_payload": {
                "supplier_id": supplier.id if supplier else None,
                "order_date": date.today(),
                "expected_date": None,
                "payment_method": "bank_transfer",
                "notes": f"Samodejni predlog GrowMaster Seed Forecast: {item['crop']} {item['variety']}",
                "items": [{
                    "supply_item_id": supply_item.id if supply_item else None,
                    "quantity": item["order_quantity"],
                    "unit_price_eur": None,
                }],
            },
            "missing_setup": [
                label for condition, label in (
                    (supplier is None, "supplier"),
                    (supply_item is None, "supply_item"),
                    (item["package_size"] is None, "package_size"),
                    (item["order_quantity"] is None, "order_quantity"),
                ) if condition
            ],
        })
    return {
        "drafts": drafts,
        "count": len(drafts),
        "message": "Osnutki so pripravljeni za obstoječi GrowMaster Purchase Order modul; pred oddajo je treba vnesti ceno.",
    }


@router.get("/api/master-data/quality")
def master_data_quality(db: Session = Depends(get_db)) -> dict:
    crops = list(db.scalars(select(Crop).options(selectinload(Crop.varieties))).all())
    rows: list[dict] = []
    required_fields = (
        "seed_rate_g_m2", "seed_spacing_cm", "row_spacing_cm", "planting_method",
        "outdoor_months", "heat_tolerance", "cold_tolerance",
    )
    totals = defaultdict(int)
    for crop in crops:
        for variety in crop.varieties:
            profile = seeding_profile(crop.name, variety.name, crop.family, crop.category)
            missing = [field for field in required_fields if getattr(variety, field, None) in (None, "")]
            if profile.get("jang_jp1", {}).get("roller") is None and profile.get("production_type") not in {"transplant"}:
                missing.append("jang_jp1_roller")
            if not list_lots(crop.name, variety.name):
                missing.append("inventory_lot")
            score = max(0, round(100 * (1 - len(missing) / (len(required_fields) + 2))))
            band = "complete" if score >= 85 else ("partial" if score >= 50 else "incomplete")
            totals[band] += 1
            rows.append({
                "crop": crop.name,
                "variety": variety.name,
                "score": score,
                "status": band,
                "missing": missing,
            })
    rows.sort(key=lambda row: (row["score"], row["crop"], row["variety"]))
    return {"summary": dict(totals), "items": rows, "count": len(rows)}


@router.get("/api/agronomy/learning")
def agronomy_learning(
    min_samples: int = Query(default=2, ge=1, le=20),
    db: Session = Depends(get_db),
) -> dict:
    plantings = list(
        db.scalars(
            select(Planting)
            .where(Planting.farm_id == DEFAULT_FARM_ID)
            .options(
                selectinload(Planting.crop), selectinload(Planting.variety),
                selectinload(Planting.bed), selectinload(Planting.harvests),
            )
        ).all()
    )
    inv = load_inventory()
    consumptions = {int(item["planting_id"]): item for item in inv.get("planting_consumptions", []) if item.get("planting_id") is not None}
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for planting in plantings:
        if not planting.harvests:
            continue
        first_harvest = min(h.harvest_date for h in planting.harvests)
        actual_dtm = (first_harvest - planting.sowing_date).days
        consumption = consumptions.get(planting.id)
        seed_rate_actual = None
        if consumption and consumption.get("status") == "consumed" and consumption.get("required_unit") == "g" and planting.bed.area_m2 > 0:
            seed_rate_actual = float(consumption.get("required_quantity", 0)) / 1.05 / planting.bed.area_m2
        grouped[(planting.crop.name, planting.variety.name)].append({
            "planting_id": planting.id,
            "actual_dtm": actual_dtm,
            "seed_rate_g_m2": seed_rate_actual,
            "yield_kg_m2": sum(h.quantity_kg for h in planting.harvests) / planting.bed.area_m2 if planting.bed.area_m2 else None,
        })

    suggestions: list[dict] = []
    for (crop_name, variety_name), samples in grouped.items():
        if len(samples) < min_samples:
            continue
        crop = next((p.crop for p in plantings if p.crop.name == crop_name), None)
        variety = next((p.variety for p in plantings if p.crop.name == crop_name and p.variety.name == variety_name), None)
        if not crop or not variety:
            continue
        dtms = [s["actual_dtm"] for s in samples if s["actual_dtm"] > 0]
        seed_rates = [s["seed_rate_g_m2"] for s in samples if s["seed_rate_g_m2"] is not None]
        yields = [s["yield_kg_m2"] for s in samples if s["yield_kg_m2"] is not None]
        actual_dtm = round(sum(dtms) / len(dtms)) if dtms else None
        actual_rate = round(sum(seed_rates) / len(seed_rates), 3) if seed_rates else None
        current_profile = seeding_profile(crop_name, variety_name, crop.family, crop.category)
        current_rate = current_profile.get("seed_rate_g_m2")
        dtm_delta = actual_dtm - variety.days_to_harvest if actual_dtm is not None else None
        rate_delta_pct = ((actual_rate / current_rate - 1) * 100) if actual_rate is not None and current_rate else None
        confidence = "high" if len(samples) >= 5 else ("medium" if len(samples) >= 3 else "low")
        suggestions.append({
            "crop": crop_name,
            "variety": variety_name,
            "samples": len(samples),
            "confidence": confidence,
            "current_days_to_harvest": variety.days_to_harvest,
            "observed_days_to_harvest": actual_dtm,
            "dtm_delta_days": dtm_delta,
            "current_seed_rate_g_m2": current_rate,
            "observed_seed_rate_g_m2": actual_rate,
            "seed_rate_delta_pct": round(rate_delta_pct, 1) if rate_delta_pct is not None else None,
            "observed_yield_kg_m2": round(sum(yields) / len(yields), 2) if yields else None,
            "recommend_seed_rate_update": bool(rate_delta_pct is not None and abs(rate_delta_pct) >= 10 and len(seed_rates) >= min_samples),
            "recommend_dtm_review": bool(dtm_delta is not None and abs(dtm_delta) >= 5),
            "sample_details": samples,
        })
    suggestions.sort(key=lambda item: (-item["samples"], item["crop"], item["variety"]))
    return {
        "min_samples": min_samples,
        "suggestions": suggestions,
        "count": len(suggestions),
        "principle": "GrowMaster predlaga spremembe na podlagi dejanskih rezultatov, master podatkov pa ne prepiše samodejno.",
    }
