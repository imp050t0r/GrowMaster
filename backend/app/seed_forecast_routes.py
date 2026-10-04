from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import CropPlan
from app.seed_inventory_service import convert_quantity, list_lots, requirement_from_target_plants
from app.seed_quantity import calculate_seed_quantity
from app.seeding_profiles import seeding_profile


router = APIRouter()
DEFAULT_FARM_ID = 1


def _package_size_for_lots(lots: list[dict], target_unit: str) -> float | None:
    sizes: list[float] = []
    for lot in lots:
        if lot.get("unit") == "pellets" and target_unit == "g":
            continue
        package_size = lot.get("package_size")
        if not package_size or package_size <= 0:
            continue
        try:
            sizes.append(
                convert_quantity(
                    package_size,
                    lot["unit"],
                    target_unit,
                    lot.get("thousand_seed_weight_g"),
                )
            )
        except ValueError:
            continue
    return min((s for s in sizes if math.isfinite(s) and s > 0), default=None)


def _allocate_lots(lots: list[dict], plans: list[dict], target_unit: str) -> dict:
    usable = []
    warnings = []
    for lot in lots:
        try:
            if lot.get("unit") == "pellets" and target_unit == "g":
                raise ValueError("Masa obloženega semena ni določena.")
            quantity = convert_quantity(lot["quantity"], lot["unit"], target_unit, lot.get("thousand_seed_weight_g"))
            if not math.isfinite(quantity) or quantity < 0:
                raise ValueError("Neveljavna količina.")
            if target_unit in ("seeds", "pellets"):
                quantity = math.floor(quantity)
            expiry = date.fromisoformat(lot["expiry_date"]) if lot.get("expiry_date") else date.max
            usable.append({"quantity": quantity, "expiry": expiry})
            if expiry == date.max:
                warnings.append({"lot_id": lot.get("id"), "message": "Rok uporabnosti ni vpisan; zaloga je vključena brez preverjenega roka."})
        except (ValueError, TypeError, KeyError):
            warnings.append({"lot_id": lot.get("id"), "message": "Zaloga ni vključena: neveljaven rok ali količina oziroma manjkajoča pretvorba enot."})
    usable.sort(key=lambda item: item["expiry"])
    shortage = 0.0
    for plan in plans:
        remaining = plan["required_quantity"]
        for lot in usable:
            if lot["expiry"] < plan["sowing_date"]:
                continue
            amount = min(remaining, lot["quantity"])
            remaining -= amount
            lot["quantity"] -= amount
        plan["shortage"] = round(remaining, 2)
        shortage += remaining
    last_date = plans[-1]["sowing_date"]
    available = sum(p["required_quantity"] for p in plans) - shortage + sum(l["quantity"] for l in usable if l["expiry"] >= last_date)
    expired = sum(l["quantity"] for l in usable if l["expiry"] < last_date)
    return {"available": available, "shortage": shortage, "expired_quantity": expired, "warnings": warnings}


def _nursery_packages(lots: list[dict], shortage: int) -> list[dict]:
    packages = []
    for lot in lots:
        try:
            size = float(lot["package_size"])
            unit = lot["unit"]
            if not math.isfinite(size) or size <= 0 or (unit in ("seeds", "pellets") and not size.is_integer()):
                continue
            count = convert_quantity(size, unit, "seeds", lot.get("thousand_seed_weight_g"))
            if not math.isfinite(count) or count < 1:
                continue
            seeds_per_package = math.floor(count)
            needed = math.ceil(shortage / seeds_per_package) if shortage else 0
            packages.append({"lot_id": lot.get("id"), "supplier": lot.get("supplier"),
                             "package_size": size, "unit": unit, "seeds_per_package": seeds_per_package,
                             "packages_to_order": needed, "order_quantity": round(needed*size, 4)})
        except (ValueError, TypeError, KeyError):
            continue
    return sorted(packages, key=lambda p: (p["packages_to_order"], p["seeds_per_package"], str(p["lot_id"])))


@router.get("/api/seed-inventory/nursery-forecast/{plan_id}")
def nursery_seed_forecast(
    plan_id: int,
    target_plants: int = Query(ge=1, le=1000000),
    germination_pct: float = Query(ge=0.01, le=100, allow_inf_nan=False),
    nursery_survival_pct: float = Query(ge=0.01, le=100, allow_inf_nan=False),
    reserve_pct: float = Query(default=5, ge=0, le=100, allow_inf_nan=False),
    db: Session = Depends(get_db),
) -> dict:
    plan = db.scalar(select(CropPlan).where(
        CropPlan.id == plan_id, CropPlan.farm_id == DEFAULT_FARM_ID,
    ).options(selectinload(CropPlan.bed), selectinload(CropPlan.crop), selectinload(CropPlan.variety)))
    if plan is None:
        raise HTTPException(status_code=404, detail="Načrt ne obstaja.")
    if plan.status != "planned":
        raise HTTPException(status_code=409, detail="Izberi še neaktiviran načrt presajanja.")
    if plan.transplant_date is None or plan.transplant_date < plan.sowing_date:
        raise HTTPException(status_code=422, detail="Izračun zahteva veljaven načrt s setvijo in presajanjem.")
    if plan.sowing_date < date.today():
        raise HTTPException(status_code=422, detail="Izračun je namenjen današnjim in prihodnjim setvam.")
    required = requirement_from_target_plants(target_plants, germination_pct, nursery_survival_pct, reserve_pct)
    lots = list_lots(plan.crop.name, plan.variety.name)
    allocation = _allocate_lots(lots, [{"sowing_date": plan.sowing_date, "required_quantity": required}], "seeds")
    shortage = int(allocation["shortage"])
    return {"crop_plan_id": plan.id, "bed": plan.bed.name, "crop": plan.crop.name, "variety": plan.variety.name,
            "sowing_date": plan.sowing_date, "transplant_date": plan.transplant_date,
            "target_plants": target_plants, "germination_pct": germination_pct,
            "nursery_survival_pct": nursery_survival_pct, "reserve_pct": reserve_pct,
            "required_quantity": required, "available_quantity": int(allocation["available"]),
            "shortage": shortage, "unit": "seeds", "status": "ORDER" if shortage else "OK",
            "expired_quantity": int(allocation["expired_quantity"]), "stock_warnings": allocation["warnings"],
            "packages": _nursery_packages(lots, shortage),
            "formula": "ceil(target_plants / (germination_pct/100 × nursery_survival_pct/100) × (1 + reserve_pct/100))",
            "note": "Samostojni izračun za en načrt z enim semenom na sadiko. Vnesena kalivost in delež uporabnih sadik veljata za ta izračun, ne potrjujeta kakovosti posameznih serij. Druge setve in rezervacije niso odštete. Zaloga se ne spreminja. Podatki o pakiranjih so iz evidence, ne ponudba dobavitelja."}


@router.get("/api/seed-inventory/forecast")
def seed_inventory_forecast(
    start_date: date | None = Query(default=None),
    horizon_days: int = Query(default=56, ge=1, le=365),
    reserve_pct: float = Query(default=5.0, ge=0, le=100),
    low_stock_buffer_pct: float = Query(default=20.0, ge=0, le=200),
    db: Session = Depends(get_db),
) -> dict:
    start = start_date or date.today()
    end = start + timedelta(days=horizon_days)

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

    grouped: dict[tuple[str, str | None, str], dict] = {}
    warnings: list[dict] = []

    for plan in plans:
        profile = seeding_profile(
            plan.crop.name,
            plan.variety.name,
            plan.crop.family,
            plan.crop.category,
        )
        seed_rate = plan.variety.seed_rate_g_m2 or profile.get("seed_rate_g_m2")
        if seed_rate is None or not math.isfinite(float(seed_rate)) or float(seed_rate) <= 0 or plan.transplant_date is not None:
            warnings.append(
                {
                    "crop_plan_id": plan.id,
                    "crop": plan.crop.name,
                    "variety": plan.variety.name,
                    "sowing_date": plan.sowing_date,
                    "status": "missing_seed_rate",
                    "message": "Načrt presajanja: uporabi izračun Seme za sadike; potreba ni vključena v gramovsko napoved." if plan.transplant_date else "Za neposredno setev manjka veljavna norma. Potreba ni vključena v skupno količino.",
                }
            )
            continue

        quantity = calculate_seed_quantity(
            seed_rate_g_m2=float(seed_rate),
            bed_width_m=plan.bed.width_m,
            bed_length_m=plan.bed.length_m,
            bed_count=1,
            reserve_percent=reserve_pct,
        )
        required = float(quantity["seed_g_total_with_reserve"])
        key = (plan.crop.name, plan.variety.name, "g")
        entry = grouped.setdefault(
            key,
            {
                "crop": plan.crop.name,
                "variety": plan.variety.name,
                "unit": "g",
                "required_quantity": 0.0,
                "plans": [],
            },
        )
        entry["required_quantity"] += required
        entry["plans"].append(
            {
                "crop_plan_id": plan.id,
                "bed_id": plan.bed.id,
                "bed": plan.bed.name,
                "sowing_date": plan.sowing_date,
                "required_quantity": round(required, 2),
                "unit": "g",
            }
        )

    results: list[dict] = []
    summary = defaultdict(int)

    for (_, _, unit), entry in grouped.items():
        lots = list_lots(entry["crop"], entry["variety"])
        allocation = _allocate_lots(lots, entry["plans"], unit)
        available = allocation["available"]
        required = round(entry["required_quantity"], 2)
        shortage = allocation["shortage"]
        package_size = _package_size_for_lots(lots, unit)
        packages_to_order = (
            math.ceil(shortage / package_size)
            if shortage > 0 and package_size and package_size > 0
            else (None if shortage > 0 else 0)
        )
        remaining_after_plan = available - required
        low_threshold = required * (low_stock_buffer_pct / 100.0)

        if shortage > 0:
            status = "ORDER"
        elif remaining_after_plan <= low_threshold:
            status = "LOW_STOCK"
        else:
            status = "OK"
        summary[status] += 1

        results.append(
            {
                **entry,
                "required_quantity": required,
                "available_quantity": round(available, 2),
                "remaining_after_plan": round(remaining_after_plan, 2),
                "shortage": round(shortage, 2),
                "package_size": round(package_size, 2) if package_size else None,
                "packages_to_order": packages_to_order,
                "order_quantity": (
                    round(packages_to_order * package_size, 2)
                    if package_size and packages_to_order
                    else None
                ),
                "status": status,
                "lot_count": len(lots),
                "expired_quantity": round(allocation["expired_quantity"], 2),
                "stock_warnings": allocation["warnings"],
                "first_shortage_date": next((p["sowing_date"] for p in entry["plans"] if p["shortage"] > 0), None),
            }
        )

    results.sort(
        key=lambda item: (
            {"ORDER": 0, "LOW_STOCK": 1, "OK": 2}[item["status"]],
            item["plans"][0]["sowing_date"],
            item["crop"],
            item["variety"] or "",
        )
    )

    return {
        "start_date": start,
        "end_date": end,
        "horizon_days": horizon_days,
        "reserve_pct": reserve_pct,
        "low_stock_buffer_pct": low_stock_buffer_pct,
        "planned_sowings": len(plans),
        "items": results,
        "warnings": warnings,
        "summary": {
            "ok": summary["OK"],
            "low_stock": summary["LOW_STOCK"],
            "order": summary["ORDER"],
            "missing_seed_rate": len(warnings),
        },
    }
