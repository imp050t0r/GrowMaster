from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.maturity import maturity_days_for_date
from app.models import Bed, Crop, CropPlan, Planting
from app.planting_advisor import (
    ROTATION_RULES,
    rotation_families,
    score_candidate,
    seasonal_assessment,
)
from app.seed_quantity import calculate_seed_quantity
from app.seeding_profiles import seeding_profile


router = APIRouter()
DEFAULT_FARM_ID = 1


def _plan_start(plan: CropPlan) -> date:
    return plan.transplant_date or plan.sowing_date


@router.get("/api/beds/{bed_id}/next-crop-suggestions")
def next_crop_suggestions(
    bed_id: int,
    start_date: date | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
    reserve_percent: float = Query(default=5.0, ge=0, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Rank the best successor crops for one bed after harvest."""
    target_date = start_date or date.today()
    history_cycles = int(ROTATION_RULES.get("history_cycles", 4))
    free_window_fit_bonus = int(ROTATION_RULES.get("free_window_fit_bonus", 10))
    free_window_overrun_penalty = int(
        ROTATION_RULES.get("free_window_overrun_penalty", -55)
    )

    bed = db.scalar(
        select(Bed).where(Bed.id == bed_id, Bed.farm_id == DEFAULT_FARM_ID)
    )
    if bed is None:
        raise HTTPException(status_code=404, detail="Gredica ne obstaja.")

    active = db.scalar(
        select(Planting)
        .where(
            Planting.bed_id == bed.id,
            Planting.farm_id == DEFAULT_FARM_ID,
            Planting.status == "active",
        )
        .options(selectinload(Planting.crop), selectinload(Planting.variety))
        .limit(1)
    )
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Gredica {bed.name} je še zasedena z {active.crop.name} "
                f"{active.variety.name}. Najprej zaključi rastni cikel."
            ),
        )

    history = list(
        db.scalars(
            select(Planting)
            .where(
                Planting.bed_id == bed.id,
                Planting.farm_id == DEFAULT_FARM_ID,
                Planting.status == "completed",
            )
            .options(
                selectinload(Planting.crop),
                selectinload(Planting.variety),
                selectinload(Planting.harvests),
            )
            .order_by(Planting.sowing_date.desc(), Planting.id.desc())
        ).all()
    )
    recent_history = history[:history_cycles]
    recent_family_sets = [
        rotation_families(
            planting.crop.name,
            planting.crop.family,
            planting.variety.name,
        )
        for planting in recent_history
    ]
    if not recent_family_sets and bed.last_crop_family:
        recent_family_sets = [{bed.last_crop_family}]

    plans = list(
        db.scalars(
            select(CropPlan)
            .where(
                CropPlan.bed_id == bed.id,
                CropPlan.farm_id == DEFAULT_FARM_ID,
                CropPlan.status == "planned",
                CropPlan.expected_harvest_date >= target_date,
            )
            .order_by(CropPlan.sowing_date, CropPlan.id)
        ).all()
    )
    future_starts = [_plan_start(plan) for plan in plans if _plan_start(plan) > target_date]
    available_until = min(future_starts) if future_starts else None
    available_days = (
        max(0, (available_until - target_date).days) if available_until else None
    )

    crops = list(
        db.scalars(
            select(Crop).options(selectinload(Crop.varieties)).order_by(Crop.name)
        ).all()
    )
    candidates: list[dict] = []

    for crop in crops:
        if not crop.varieties:
            continue
        variety = min(
            crop.varieties,
            key=lambda item: (maturity_days_for_date(item, target_date), item.name),
        )
        maturity_days = maturity_days_for_date(variety, target_date)
        expected_harvest = target_date + timedelta(days=maturity_days)
        families = rotation_families(crop.name, crop.family, variety.name)

        overlapping_plans = [
            plan
            for plan in plans
            if _plan_start(plan) <= expected_harvest
            and plan.expected_harvest_date >= target_date
        ]
        has_plan_conflict = bool(overlapping_plans)

        previous_yields = [
            sum(harvest.quantity_kg for harvest in planting.harvests) / bed.area_m2
            for planting in history
            if planting.crop_id == crop.id and planting.harvests and bed.area_m2 > 0
        ]
        previous_yield_per_m2 = (
            round(sum(previous_yields) / len(previous_yields), 2)
            if previous_yields
            else None
        )
        expected_yield_kg = (
            round(previous_yield_per_m2 * bed.area_m2, 2)
            if previous_yield_per_m2 is not None
            else None
        )

        seasonal_score, seasonal_reason, seasonal_warning = seasonal_assessment(
            crop.name, crop.category, target_date
        )
        if seasonal_score <= -60:
            continue

        result = score_candidate(
            families,
            recent_family_sets,
            maturity_days,
            seasonal_score,
            has_plan_conflict,
            previous_yield_per_m2,
        )
        result["reasons"].insert(0, seasonal_reason)
        if seasonal_warning:
            result["warnings"].append(seasonal_warning)

        fits_free_window = available_days is None or maturity_days < available_days
        if available_days is not None:
            if fits_free_window:
                result["score"] += free_window_fit_bonus
                result["reasons"].append(
                    f"Cikel se prilega v {available_days}-dnevno prosto okno gredice."
                )
            else:
                result["score"] = max(
                    0, result["score"] + free_window_overrun_penalty
                )
                result["warnings"].append(
                    f"Cikel ({maturity_days} dni) je predolg za {available_days}-dnevno prosto okno."
                )

        rotation_safe = not any(
            families & previous_families
            for previous_families in recent_family_sets[:history_cycles]
        )
        seeding = seeding_profile(
            crop.name,
            variety.name,
            crop.family,
            crop.category,
        )
        seed_quantity = calculate_seed_quantity(
            seeding.get("seed_rate_g_m2"),
            bed.width_m,
            bed.length_m,
            1,
            reserve_percent,
        )

        candidates.append(
            {
                "crop_id": crop.id,
                "crop": crop.name,
                "crop_family": crop.family,
                "variety_id": variety.id,
                "variety": variety.name,
                "sowing_date": target_date,
                "expected_harvest_date": expected_harvest,
                "maturity_days": maturity_days,
                "rotation_safe": rotation_safe,
                "fits_free_window": fits_free_window,
                "has_plan_conflict": has_plan_conflict,
                "previous_yield_kg_m2": previous_yield_per_m2,
                "expected_yield_kg": expected_yield_kg,
                "seeding": seeding,
                "seed_quantity": seed_quantity,
                **result,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["has_plan_conflict"],
            not item["rotation_safe"],
            not item["fits_free_window"],
            -item["score"],
            item["maturity_days"],
            item["crop"],
        )
    )

    return {
        "bed_id": bed.id,
        "bed": bed.name,
        "bed_width_m": bed.width_m,
        "bed_length_m": bed.length_m,
        "bed_area_m2": bed.area_m2,
        "start_date": target_date,
        "available_until": available_until,
        "available_days": available_days,
        "seed_reserve_percent": reserve_percent,
        "last_crop_family": bed.last_crop_family,
        "history": [
            {
                "crop": planting.crop.name,
                "variety": planting.variety.name,
                "sowing_date": planting.sowing_date,
                "families": sorted(
                    rotation_families(
                        planting.crop.name,
                        planting.crop.family,
                        planting.variety.name,
                    )
                ),
            }
            for planting in recent_history
        ],
        "suggestions": candidates[:limit],
        "message": (
            "Naslednje kulture so razvrščene glede na kolobar, termin, DTM, "
            "prosto časovno okno, obstoječe načrte, pridelek, sejalniški profil "
            "in izračun količine semena za dejansko gredico."
        ),
        "note": (
            "Predlog ne nadomešča presoje tal, bolezni, vremena, kalibracije sejalnice "
            "in razpoložljive zaščite."
        ),
    }
