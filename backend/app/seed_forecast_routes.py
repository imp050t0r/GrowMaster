from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import CropPlan
from app.seed_inventory_service import convert_quantity, list_lots
from app.seed_quantity import calculate_seed_quantity
from app.seeding_profiles import seeding_profile


router = APIRouter()
DEFAULT_FARM_ID = 1


def _package_size_for_lots(lots: list[dict], target_unit: str) -> float | None:
    sizes: list[float] = []
    for lot in lots:
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
    return min(sizes) if sizes else None


def _available_quantity(lots: list[dict], target_unit: str) -> float:
    total = 0.0
    for lot in lots:
        try:
            total += convert_quantity(
                lot["quantity"],
                lot["unit"],
                target_unit,
                lot.get("thousand_seed_weight_g"),
            )
        except ValueError:
            continue
    return total


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
        seed_rate = profile.get("seed_rate_g_m2")
        if seed_rate is None:
            warnings.append(
                {
                    "crop_plan_id": plan.id,
                    "crop": plan.crop.name,
                    "variety": plan.variety.name,
                    "sowing_date": plan.sowing_date,
                    "status": "missing_seed_rate",
                    "message": "Za ta crop plan ni dovolj podatkov za zanesljiv izračun potrebne količine semena.",
                }
            )
            continue

        quantity = calculate_seed_quantity(
            seed_rate_g_m2=float(seed_rate),
            bed_width_m=plan.bed.width_m,
            bed_length_m=plan.bed.length_m,
            bed_count=1,
            reserve_pct=reserve_pct,
        )
        required = float(quantity["total_grams_with_reserve"])
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
        available = _available_quantity(lots, unit)
        required = round(entry["required_quantity"], 2)
        shortage = max(0.0, required - available)
        package_size = _package_size_for_lots(lots, unit)
        packages_to_order = (
            math.ceil(shortage / package_size)
            if shortage > 0 and package_size and package_size > 0
            else 0
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
