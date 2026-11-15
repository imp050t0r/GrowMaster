"""Manual nutrient records and reviewed applications; no agronomic dose inference."""
import hashlib
import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Bed, Planting, Harvest, FertilizationSoilTest as SoilTest
from app.models import FertilizationPlan as Plan, FertilizationApplication as Application

router = APIRouter(prefix="/api/fertilization")
FARM_ID = 1


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class SoilInput(Input):
    sampled_on: date
    source: str = Field(min_length=1, max_length=300)
    sample_area: str = Field(min_length=1, max_length=300)
    method: str = Field(min_length=1, max_length=200)
    ph: float | None = Field(default=None, ge=0, le=14)
    organic_matter_pct: float | None = Field(default=None, ge=0, le=100)
    phosphorus: float | None = Field(default=None, ge=0)
    potassium: float | None = Field(default=None, ge=0)
    nutrient_unit: str = Field(min_length=1, max_length=80)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def check_sample(self):
        if self.sampled_on > date.today():
            raise ValueError("Datum vzorčenja ne sme biti v prihodnosti.")
        if all(v is None for v in (self.ph, self.organic_matter_pct, self.phosphorus, self.potassium)):
            raise ValueError("Vnesi vsaj en rezultat analize.")
        return self


class DoseInput(Input):
    day: date
    area_m2: float = Field(gt=0, le=1000000)
    material: str = Field(min_length=1, max_length=200)
    quantity_kg: float = Field(gt=0, le=1000000)
    n_pct: float | None = Field(default=None, ge=0, le=100)
    p2o5_pct: float | None = Field(default=None, ge=0, le=100)
    k2o_pct: float | None = Field(default=None, ge=0, le=100)
    composition_source: str = Field(default="", max_length=300)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def check_composition(self):
        values = (self.n_pct, self.p2o5_pct, self.k2o_pct)
        if any(v is not None for v in values) and not self.composition_source:
            raise ValueError("Navedi vir deklarirane sestave.")
        if sum(v or 0 for v in values) > 100:
            raise ValueError("Vsota deležev N, P₂O₅ in K₂O presega 100 %.")
        return self


class ApplicationInput(DoseInput):
    planting_id: int | None = Field(default=None, gt=0, strict=True)


class PlanInput(DoseInput):
    planting_id: int = Field(gt=0, strict=True)
    rationale: str = Field(min_length=1, max_length=2000)
    context_version: str = Field(min_length=64, max_length=64)


class Confirmation(Input):
    reviewer: str = Field(min_length=1, max_length=120)
    context_version: str = Field(min_length=64, max_length=64)


class Completion(Input):
    applied_on: date


class VoidInput(Input):
    reason: str = Field(min_length=1, max_length=1000)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def bed_for(db, bed_id):
    bed = db.scalar(select(Bed).where(Bed.id == bed_id, Bed.farm_id == FARM_ID))
    if bed is None:
        raise HTTPException(404, "Gredica ne obstaja.")
    return bed


def planting_for(db, planting_id, bed_id, active=False):
    row = db.scalar(select(Planting).where(Planting.id == planting_id,
        Planting.farm_id == FARM_ID, Planting.bed_id == bed_id))
    if row is None:
        raise HTTPException(404, "Posevek ne pripada tej gredici.")
    if active and row.status != "active":
        raise HTTPException(409, "Načrt zahteva aktiven posevek.")
    return row


def check_dose(db, bed, payload, active=False):
    if payload.area_m2 > bed.area_m2:
        raise HTTPException(422, "Obravnavana površina presega površino gredice.")
    if payload.planting_id is not None:
        planting_for(db, payload.planting_id, bed.id, active)


def rows_for(db, model, bed_id):
    return db.scalars(select(model).where(model.farm_id == FARM_ID,
        model.bed_id == bed_id).order_by(model.id)).all()


def context_for(db, bed):
    plantings = [{"id": p.id, "crop_id": p.crop_id, "crop": p.crop.name,
        "variety": p.variety.name, "status": p.status, "sowing_date": str(p.sowing_date),
        "completed_on": str(p.completed_on) if p.completed_on else None}
        for p in rows_for(db, Planting, bed.id)]
    harvests = [{"id": h.id, "planting_id": h.planting_id, "day": str(h.harvest_date),
        "quantity_kg": h.quantity_kg} for h in rows_for(db, Harvest, bed.id)]
    soil = [{"id": s.id, **json.loads(s.parameters)} for s in rows_for(db, SoilTest, bed.id)]
    applications = [{"id": a.id, "planting_id": a.planting_id, "plan_id": a.plan_id,
        "void_reason": a.void_reason, **json.loads(a.parameters)}
        for a in rows_for(db, Application, bed.id)]
    value = {"bed_id": bed.id, "area_m2": bed.area_m2, "plantings": plantings,
        "harvests": harvests, "soil_tests": soil, "applications": applications}
    return value, hashlib.sha256(encode(value).encode()).hexdigest()


def plan_data(plan, version):
    return {"id": plan.id, "status": plan.status, "reviewer": plan.reviewer,
        "confirmed_at": plan.confirmed_at, "stale": hashlib.sha256(plan.context.encode()).hexdigest() != version,
        **json.loads(plan.parameters)}


@router.get("/beds/{bed_id}")
def overview(bed_id: int, db: Session = Depends(get_db)):
    bed = bed_for(db, bed_id)
    context, version = context_for(db, bed)
    actual = [a for a in context["applications"] if not a["void_reason"]]
    totals = {}
    for nutrient in ("n", "p2o5", "k2o"):
        key = nutrient + "_pct"
        totals[nutrient] = {"known_kg": round(sum(a["quantity_kg"] * a[key] / 100
            for a in actual if a[key] is not None), 6),
            "unknown_applications": sum(a[key] is None for a in actual)}
    return {**context, "context_version": version, "declared_totals": totals,
        "plans": [plan_data(p, version) for p in rows_for(db, Plan, bed_id)],
        "automatic_execution": False,
        "warnings": (["Manjka analiza tal."] if not context["soil_tests"] else []) + [
            "Vsote so deklarirani vnosi vseh evidentiranih let, ne zaloga dostopnih hranil v tleh.",
            "Potrebe kulture, mineralizacija in ostanki zahtevajo strokovno presojo; odmerki niso samodejno izračunani."]}


@router.post("/beds/{bed_id}/soil-tests", status_code=201)
def add_soil(bed_id: int, payload: SoilInput, db: Session = Depends(get_db)):
    bed_for(db, bed_id)
    row = SoilTest(farm_id=FARM_ID, bed_id=bed_id, sampled_on=payload.sampled_on,
        parameters=encode(payload.model_dump(mode="json")))
    db.add(row); db.commit()
    return {"id": row.id}


@router.post("/beds/{bed_id}/applications", status_code=201)
def add_application(bed_id: int, payload: ApplicationInput, db: Session = Depends(get_db)):
    bed = bed_for(db, bed_id)
    check_dose(db, bed, payload)
    if payload.day > date.today():
        raise HTTPException(422, "Izvedeno gnojenje ne more biti v prihodnosti.")
    row = Application(farm_id=FARM_ID, bed_id=bed_id, planting_id=payload.planting_id,
        applied_on=payload.day, parameters=encode(payload.model_dump(mode="json", exclude={"planting_id"})))
    db.add(row); db.commit()
    return {"id": row.id}


@router.post("/beds/{bed_id}/plans", status_code=201)
def add_plan(bed_id: int, payload: PlanInput, db: Session = Depends(get_db)):
    bed = bed_for(db, bed_id)
    check_dose(db, bed, payload, active=True)
    if payload.day < date.today():
        raise HTTPException(422, "Nov načrt ne more biti v preteklosti.")
    context, version = context_for(db, bed)
    if payload.context_version != version:
        raise HTTPException(409, "Podatki gredice so se spremenili. Osveži pregled.")
    row = Plan(farm_id=FARM_ID, bed_id=bed_id, planting_id=payload.planting_id,
        parameters=encode(payload.model_dump(mode="json", exclude={"context_version"})), context=encode(context))
    db.add(row); db.commit()
    return {"id": row.id}


def plan_for(db, plan_id):
    row = db.scalar(select(Plan).where(Plan.id == plan_id, Plan.farm_id == FARM_ID))
    if row is None:
        raise HTTPException(404, "Načrt ne obstaja.")
    return row


def current_plan(db, row):
    bed = bed_for(db, row.bed_id)
    planting_for(db, row.planting_id, row.bed_id, active=True)
    _, version = context_for(db, bed)
    if hashlib.sha256(row.context.encode()).hexdigest() != version:
        raise HTTPException(409, "Podlaga načrta se je spremenila. Prekliči ga in pripravi nov načrt.")
    return version


@router.post("/plans/{plan_id}/confirm")
def confirm_plan(plan_id: int, payload: Confirmation, db: Session = Depends(get_db)):
    row = plan_for(db, plan_id)
    version = current_plan(db, row)
    if payload.context_version != version:
        raise HTTPException(409, "Osveži pregled gredice.")
    result = db.execute(update(Plan).where(Plan.id == row.id, Plan.status == "draft").values(
        status="confirmed", reviewer=payload.reviewer, confirmed_at=datetime.now(timezone.utc)))
    if result.rowcount != 1:
        db.rollback(); raise HTTPException(409, "Načrt ni več osnutek.")
    db.commit()
    return {"status": "confirmed"}


@router.post("/plans/{plan_id}/complete", status_code=201)
def complete_plan(plan_id: int, payload: Completion, db: Session = Depends(get_db)):
    row = plan_for(db, plan_id)
    if payload.applied_on > date.today():
        raise HTTPException(422, "Datum izvedbe ne sme biti v prihodnosti.")
    if row.confirmed_at is None or payload.applied_on < row.confirmed_at.date():
        raise HTTPException(409, "Izvedba mora slediti potrditvi načrta.")
    current_plan(db, row)
    result = db.execute(update(Plan).where(Plan.id == row.id, Plan.status == "confirmed").values(status="applied"))
    if result.rowcount != 1:
        db.rollback(); raise HTTPException(409, "Načrt ni potrjen ali je že izveden.")
    data = json.loads(row.parameters)
    dose = {k: data[k] for k in DoseInput.model_fields}
    dose["day"] = str(payload.applied_on)
    application = Application(farm_id=FARM_ID, bed_id=row.bed_id, planting_id=row.planting_id,
        plan_id=row.id, applied_on=payload.applied_on, parameters=encode(dose))
    db.add(application); db.commit()
    return {"id": application.id, "status": "applied"}


@router.post("/plans/{plan_id}/cancel")
def cancel_plan(plan_id: int, db: Session = Depends(get_db)):
    row = plan_for(db, plan_id)
    result = db.execute(update(Plan).where(Plan.id == row.id, Plan.status.in_(["draft", "confirmed"])).values(status="cancelled"))
    if result.rowcount != 1:
        db.rollback(); raise HTTPException(409, "Načrta ni mogoče preklicati.")
    db.commit()
    return {"status": "cancelled"}


@router.post("/applications/{application_id}/void")
def void_application(application_id: int, payload: VoidInput, db: Session = Depends(get_db)):
    row = db.scalar(select(Application).where(Application.id == application_id, Application.farm_id == FARM_ID))
    if row is None:
        raise HTTPException(404, "Vnos ne obstaja.")
    row.void_reason = payload.reason
    db.commit()
    return {"id": row.id, "void_reason": row.void_reason}
