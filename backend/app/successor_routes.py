from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from pydantic import BaseModel, ConfigDict, Field

from app.database import get_db
from app.adaptive_recommendations import apply_yield_evidence, yield_evidence
from app.maturity import maturity_days_for_date
from app.models import Bed, Crop, CropPlan, Harvest, Planting, Task
from app.planting_advisor import (
    ROTATION_RULES,
    rotation_families,
    score_candidate,
    seasonal_assessment,
)
from app.seed_quantity import calculate_seed_quantity
from app.seeding_profiles import seeding_profile
from app.dynamic_dtm import store_prediction
from app.succession import review as succession_review
from app.harvest_comparison import harvest_report
from app.dtm_learning import learning_report, apply_suggestion, save_result, snapshot
from app.workload import workload_report
from app.harvest_forecast import harvest_forecast


router = APIRouter()
DEFAULT_FARM_ID = 1


@router.get("/api/planning/harvest-forecast")
def get_harvest_forecast(start: date, end: date, db: Session = Depends(get_db)) -> dict:
    if end < start or (end-start).days > 366:
        raise HTTPException(status_code=422, detail="Izberi veljavno obdobje, dolgo največ 367 dni.")
    plans = db.scalars(select(CropPlan).where(
        CropPlan.farm_id == DEFAULT_FARM_ID, CropPlan.status.in_(["planned", "activated"]),
    ).options(selectinload(CropPlan.bed), selectinload(CropPlan.crop), selectinload(CropPlan.variety))).all()
    plantings = db.scalars(select(Planting).where(
        Planting.farm_id == DEFAULT_FARM_ID, Planting.status == "active",
    ).options(selectinload(Planting.bed), selectinload(Planting.crop), selectinload(Planting.variety))).all()
    harvests = db.scalars(select(Harvest).join(Planting).where(
        Harvest.farm_id == DEFAULT_FARM_ID, Planting.farm_id == DEFAULT_FARM_ID,
    )).all()
    return harvest_forecast(plans, plantings, harvests, start, end)


@router.get("/api/planning/workload")
def get_workload(start: date, end: date, db: Session = Depends(get_db)) -> dict:
    if end < start or (end-start).days > 366:
        raise HTTPException(status_code=422, detail="Izberi veljavno obdobje, dolgo največ 367 dni.")
    from app.main import planning_calendar
    events=planning_calendar(start=start,end=end,db=db)["events"]
    pending=db.scalars(select(Task).where(
        Task.farm_id == DEFAULT_FARM_ID, Task.status == "planned",
        Task.due_date >= start, Task.due_date <= end,
    ).options(selectinload(Task.bed))).all()
    completed=db.scalars(select(Task).where(
        Task.farm_id == DEFAULT_FARM_ID, Task.status == "completed",
    ).options(selectinload(Task.bed))).all()
    return workload_report(events,pending,completed,start,end)


class SuccessionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(pattern=r"^[a-f0-9]{64}$")


class BedReleaseUpdate(SuccessionAction):
    expected_bed_release_date: date | None


class SuccessionMove(SuccessionAction):
    bed_id: int = Field(gt=0)


def succession_state(db: Session, *, lock=False):
    beds_query = select(Bed).where(Bed.farm_id == DEFAULT_FARM_ID).order_by(Bed.id)
    plans_query = select(CropPlan).where(
        CropPlan.farm_id == DEFAULT_FARM_ID, CropPlan.status == "planned"
    ).order_by(CropPlan.id).options(selectinload(CropPlan.variety), selectinload(CropPlan.crop), selectinload(CropPlan.bed))
    plantings_query = select(Planting).where(
        Planting.farm_id == DEFAULT_FARM_ID, Planting.status.in_(["active", "completed"])
    ).order_by(Planting.id).options(selectinload(Planting.variety), selectinload(Planting.crop))
    if lock:
        beds_query = beds_query.with_for_update()
        plans_query = plans_query.with_for_update()
        plantings_query = plantings_query.with_for_update()
    beds = list(db.scalars(beds_query).all())
    plans = list(db.scalars(plans_query).all())
    plantings = list(db.scalars(plantings_query).all())
    return beds, plans, plantings, succession_review(beds, plans, plantings)


def checked_succession_state(db: Session, token: str):
    state = succession_state(db, lock=True)
    if state[3]["token"] != token:
        raise HTTPException(status_code=409, detail="Načrt ali napoved se je spremenila. Osveži pregled sukcesij in ponovno preveri predlog.")
    return state


@router.get("/api/planning/successions")
def get_successions(db: Session = Depends(get_db)) -> dict:
    return succession_state(db)[3]


@router.put("/api/planning/successions/{record_type}/{record_id}/release")
def update_bed_release(record_type: str, record_id: int, payload: BedReleaseUpdate,
                       db: Session = Depends(get_db)) -> dict:
    _, plans, plantings, _ = checked_succession_state(db, payload.token)
    records = {"plans": plans, "plantings": [p for p in plantings if p.status == "active"]}.get(record_type, [])
    record = next((p for p in records if p.id == record_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Odprt zapis ne obstaja.")
    minimum = max(date.today(), record.expected_harvest_date) if record_type == "plantings" else record.expected_harvest_date
    if payload.expected_bed_release_date and payload.expected_bed_release_date < minimum:
        raise HTTPException(status_code=422, detail=f"Zaključek zasedenosti mora biti {minimum} ali pozneje. Dejansko končan cikel zaključi v gredicah.")
    record.expected_bed_release_date = payload.expected_bed_release_date
    db.commit()
    return {"message": "Predvideni zaključek zasedenosti je shranjen."}


@router.post("/api/planning/successions/{bed_id}/apply")
def apply_succession(bed_id: int, payload: SuccessionAction, db: Session = Depends(get_db)) -> dict:
    _, plans, _, report = checked_succession_state(db, payload.token)
    group = next((g for g in report["beds"] if g["bed_id"] == bed_id), None)
    if group is None:
        raise HTTPException(status_code=404, detail="Gredica nima načrtovanih sukcesij.")
    if not group["can_apply"]:
        raise HTTPException(status_code=409, detail="Predlog ni pripravljen za uporabo. Dopolni zaključke zasedenosti oziroma preveri že začete setve.")
    by_id = {p.id: p for p in plans}
    changed = []
    for row in group["plans"]:
        if not row["shift_days"]:
            continue
        plan = by_id[row["plan_id"]]
        before = row["original"]
        for name, value in row["proposed"].items():
            setattr(plan, name, value)
        # Temperatures anchored to the old dates cannot be silently reused.
        # The initial snapshot remains intact for planned-versus-actual work.
        store_prediction(plan, plan.variety)
        changed.append({"plan_id": plan.id, "before": before, "after": row["proposed"]})
    db.commit()
    return {"message": f"Posodobljenih je {len(changed)} načrtov. Razmik med setvijo sadik in presajanjem je ohranjen.", "changes": changed}


@router.post("/api/planning/successions/plans/{plan_id}/move")
def move_succession(plan_id: int, payload: SuccessionMove, db: Session = Depends(get_db)) -> dict:
    _, plans, _, report = checked_succession_state(db, payload.token)
    row = next((r for g in report["beds"] for r in g["plans"] if r["plan_id"] == plan_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Načrt ne obstaja.")
    if payload.bed_id not in {b["id"] for b in row["alternative_beds"]}:
        raise HTTPException(status_code=409, detail="Gredica ni več med preverjenimi možnostmi. Osveži pregled.")
    plan = next(p for p in plans if p.id == plan_id)
    plan.bed_id = payload.bed_id
    db.commit()
    return {"message": "Načrt je prestavljen na preverjeno prazno gredico enakih mer; datumi ostanejo ohranjeni."}


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
    all_completed = list(db.scalars(
        select(Planting).where(Planting.farm_id == DEFAULT_FARM_ID, Planting.status == "completed")
        .options(selectinload(Planting.harvests))
    ).all())
    bed_areas = {item.id: item.area_m2 for item in db.scalars(
        select(Bed).where(Bed.farm_id == DEFAULT_FARM_ID)
    ).all()}
    learned_yields = yield_evidence(all_completed, bed_areas)
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
            None,
        )
        apply_yield_evidence(result, learned_yields.get((bed.id, crop.id)))
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


@router.get("/api/planning/harvest-comparison")
def get_harvest_comparison(db: Session = Depends(get_db)) -> dict:
    plantings = db.scalars(select(Planting).where(
        Planting.farm_id == DEFAULT_FARM_ID,
        Planting.status.in_(["active", "completed"]),
    ).order_by(Planting.sowing_date.desc(), Planting.id.desc()).options(
        selectinload(Planting.harvests), selectinload(Planting.crop),
        selectinload(Planting.variety), selectinload(Planting.bed),
    )).all()
    return harvest_report(plantings)


def dtm_learning_state(db: Session, *, lock=False):
    plans_query = select(CropPlan).where(
        CropPlan.farm_id == DEFAULT_FARM_ID, CropPlan.status == "planned",
    ).order_by(CropPlan.id).options(
        selectinload(CropPlan.variety), selectinload(CropPlan.crop), selectinload(CropPlan.bed),
    )
    history_query = select(Planting).where(
        Planting.farm_id == DEFAULT_FARM_ID, Planting.status == "completed",
    ).order_by(Planting.id).options(
        selectinload(Planting.harvests), selectinload(Planting.variety),
        selectinload(Planting.crop), selectinload(Planting.bed),
    )
    if lock:
        plans_query = plans_query.with_for_update()
        history_query = history_query.with_for_update()
    plans = list(db.scalars(plans_query).all())
    history = list(db.scalars(history_query).all())
    return plans, learning_report(plans, history)


@router.get("/api/planning/dtm-learning")
def get_dtm_learning(db: Session = Depends(get_db)) -> dict:
    return dtm_learning_state(db)[1]


@router.post("/api/planning/dtm-learning/{plan_id}/{action}")
def confirm_dtm_learning(plan_id: int, action: str, payload: SuccessionAction,
                         db: Session = Depends(get_db)) -> dict:
    if action not in ("apply", "reset"):
        raise HTTPException(status_code=404, detail="Neznano dejanje.")
    plans, report = dtm_learning_state(db, lock=True)
    if payload.token != report["token"]:
        raise HTTPException(status_code=409, detail="Načrt ali zgodovina se je spremenila. Osveži predlog.")
    plan = next((p for p in plans if p.id == plan_id), None)
    row = next((r for r in report["rows"] if r["plan_id"] == plan_id), None)
    if plan is None or row is None:
        raise HTTPException(status_code=404, detail="Odprt načrt ne obstaja.")
    if action == "apply":
        if not row["can_apply"]:
            raise HTTPException(status_code=409, detail="Za ta načrt ni primernega predloga popravka.")
        apply_suggestion(plan, row)
        message = "Potrjeni popravek napovedi je shranjen za ta načrt."
    else:
        if not row["can_reset"]:
            raise HTTPException(status_code=409, detail="Popravek je mogoče odstraniti samo pred začetkom načrta.")
        baseline = snapshot(plan.dynamic_dtm_explanation)["history_correction"]["baseline"]
        save_result(plan, baseline)
        message = "Obnovljena je napoved pred potrjenim popravkom."
    db.commit()
    return {"message": message}
