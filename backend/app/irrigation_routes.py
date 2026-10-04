"""Manual, advisory water balance. No weather polling or valve commands."""
import json
import math
from datetime import date, datetime, timezone, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Bed, Crop, IrrigationBedProfile, IrrigationCropProfile, IrrigationDailyReport

router = APIRouter(prefix="/api/irrigation")
FARM_ID = 1


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class CropProfile(Input):
    kc_initial: float = Field(ge=0, le=2)
    kc_mid: float = Field(ge=0, le=2)
    kc_late: float = Field(ge=0, le=2)
    root_depth_m: float = Field(gt=0, le=3)
    depletion_fraction: float = Field(gt=0, lt=1)
    source: str = Field(min_length=1, max_length=500)


class BedProfile(Input):
    field_capacity_pct: float = Field(gt=0, le=70)
    wilting_point_pct: float = Field(ge=0, lt=70)
    efficiency_pct: float = Field(gt=0, le=100)
    flow_l_min: float | None = Field(default=None, gt=0, le=10000)
    max_application_mm: float = Field(gt=0, le=100)
    sensor_dry_pct: float | None = Field(default=None, ge=0, le=100)
    sensor_wet_pct: float | None = Field(default=None, ge=0, le=100)
    source: str = Field(min_length=1, max_length=500)
    opensprinkler_station_entity: str | None = Field(default=None, pattern=r"^switch\.[a-z0-9_]+$", max_length=150)
    max_run_seconds: int = Field(default=3600, ge=1, le=86400)

    @model_validator(mode="after")
    def ordered(self):
        if self.wilting_point_pct >= self.field_capacity_pct:
            raise ValueError("Točka venenja mora biti manjša od poljske kapacitete.")
        if (self.sensor_dry_pct is None) != (self.sensor_wet_pct is None):
            raise ValueError("Vnesi oba umerjena praga WH52 ali nobenega.")
        if self.sensor_dry_pct is not None and self.sensor_dry_pct >= self.sensor_wet_pct:
            raise ValueError("Suhi prag WH52 mora biti manjši od mokrega.")
        return self


class DayInput(Input):
    bed_id: int = Field(gt=0)
    crop_id: int = Field(gt=0)
    day: date
    stage: Literal["initial", "mid", "late"]
    initial_depletion_mm: float = Field(ge=0, le=2100)
    eto_mm: float | None = Field(default=None, ge=0, le=30)
    effective_rain_mm: float = Field(ge=0, le=500)
    applied_irrigation_mm: float = Field(ge=0, le=100)
    weather_source: str = Field(min_length=1, max_length=500)
    soil_moisture_pct: float | None = Field(default=None, ge=0, le=100)
    sensor_observed_at: datetime | None = None

    @model_validator(mode="after")
    def dates(self):
        if self.day > date.today():
            raise ValueError("Dnevna bilanca zahteva današnji ali pretekli datum.")
        if (self.soil_moisture_pct is None) != (self.sensor_observed_at is None):
            raise ValueError("Meritev WH52 zahteva tudi čas meritve.")
        if self.sensor_observed_at is not None and self.sensor_observed_at.utcoffset() is None:
            raise ValueError("Čas meritve mora vsebovati časovni pas.")
        return self


def entity(db, model, identifier):
    stmt = select(model).where(model.id == identifier)
    if model is Bed:
        stmt = stmt.where(Bed.farm_id == FARM_ID)
    row = db.scalar(stmt)
    if row is None:
        raise HTTPException(404, "Kultura ali gredica ne obstaja.")
    return row


def profile_row(db, model, key, identifier):
    return db.scalar(select(model).where(model.farm_id == FARM_ID, getattr(model, key) == identifier))


@router.get("/profiles")
def profiles(db: Session = Depends(get_db)):
    return {"crops": [{"crop_id": r.crop_id, **json.loads(r.parameters)} for r in
                      db.scalars(select(IrrigationCropProfile).where(IrrigationCropProfile.farm_id == FARM_ID))],
            "beds": [{"bed_id": r.bed_id, **BedProfile.model_validate_json(r.parameters).model_dump()} for r in
                     db.scalars(select(IrrigationBedProfile).where(IrrigationBedProfile.farm_id == FARM_ID))]}


def save_profile(db, model, key, identifier, payload):
    row = profile_row(db, model, key, identifier)
    if row is None:
        row = model(farm_id=FARM_ID, **{key: identifier})
        db.add(row)
    row.parameters = payload.model_dump_json()
    db.commit()
    return {key: identifier, **payload.model_dump()}


@router.put("/crops/{crop_id}")
def save_crop(crop_id: int, payload: CropProfile, db: Session = Depends(get_db)):
    entity(db, Crop, crop_id)
    return save_profile(db, IrrigationCropProfile, "crop_id", crop_id, payload)


@router.put("/beds/{bed_id}")
def save_bed(bed_id: int, payload: BedProfile, db: Session = Depends(get_db)):
    entity(db, Bed, bed_id)
    return save_profile(db, IrrigationBedProfile, "bed_id", bed_id, payload)


def calculate(payload: DayInput, bed: Bed, cp: CropProfile | None, bp: BedProfile | None):
    result = {"bed_id": bed.id, "bed": bed.name, "crop_id": payload.crop_id,
              "day": str(payload.day), "inputs": payload.model_dump(mode="json"),
              "status": "missing_data", "confidence": "low", "automatic_execution": False,
              "gross_mm": None, "litres": None, "minutes": None, "warnings": [],
              "note": "Ročna dnevna ocena za eno gredico; ni ukaz za ventil ali skupno cono. "
                      "Začetni primanjkljaj potrdi za vsak dan; shranjeni izračuni ga ne prenašajo samodejno. "
                      "Priporočeno zalivanje ni evidentirano kot izvedeno."}
    missing = [name for name, value in (("profil kulture", cp), ("profil grede", bp), ("ET₀", payload.eto_mm)) if value is None]
    if missing:
        result["warnings"].append("Manjka: " + ", ".join(missing))
        return result
    result["crop_profile"] = cp.model_dump()
    result["bed_profile"] = bp.model_dump()
    capacity = 1000 * (bp.field_capacity_pct - bp.wilting_point_pct) / 100 * cp.root_depth_m
    if payload.initial_depletion_mm > capacity:
        raise HTTPException(422, "Začetni primanjkljaj presega razpoložljivo vodo v koreninah.")
    kc = getattr(cp, "kc_" + payload.stage)
    etc = payload.eto_mm * kc
    # Fixed user-selected p, no automatic growth, capillary rise or runoff model.
    threshold = capacity * cp.depletion_fraction
    raw_balance = payload.initial_depletion_mm + etc - payload.effective_rain_mm - payload.applied_irrigation_mm * bp.efficiency_pct / 100
    deficit = min(capacity, max(0, raw_balance))
    required = deficit >= threshold
    result.update(taw_mm=round(capacity, 3), raw_mm=round(threshold, 3), kc=kc,
                  etc_mm=round(etc, 3), depletion_mm=round(deficit, 3), area_m2=bed.area_m2,
                  status="irrigate" if required else "hold", confidence="low")
    result["warnings"].append("Ročni ET₀, faza rasti in začetna bilanca; profili zahtevajo lokalno preverjanje. WH52 ne predstavlja cele grede.")
    if raw_balance > capacity:
        result["warnings"].append("Ocenjeno izsuševanje presega kapaciteto; možen vodni stres. ETc ni popravljena za stres.")
    if payload.soil_moisture_pct is not None:
        now = datetime.now(timezone.utc)
        if payload.day != date.today() or not timedelta(0) <= now - payload.sensor_observed_at <= timedelta(hours=6):
            result["status"] = "review"
            result["warnings"].append("WH52: meritev ni današnja sveža meritev (največ 6 ur) ali je v prihodnosti.")
        elif bp.sensor_dry_pct is None:
            result["status"] = "review"
            result["warnings"].append("WH52 nima umerjenih suhih in mokrih pragov.")
        elif (required and payload.soil_moisture_pct >= bp.sensor_wet_pct) or (not required and payload.soil_moisture_pct <= bp.sensor_dry_pct):
            result["status"] = "review"
            result["warnings"].append("WH52 in vodna bilanca se ne ujemata; preveri tla in začetni primanjkljaj.")
    else:
        result["warnings"].append("Brez preverjanja z WH52; izračun je samo ocena vodne bilance.")
    if bed.area_m2 <= 0:
        result["status"] = "review"
        result["warnings"].append("Površina grede ni veljavna.")
    if result["status"] == "review":
        return result
    uncapped = deficit / (bp.efficiency_pct / 100) if required else 0
    gross = min(bp.max_application_mm, uncapped)
    if uncapped > gross:
        result["warnings"].append("Količina je omejena z največjim enkratnim odmerkom; po zalivanju ponovno preveri tla.")
    litres = gross * bed.area_m2
    result.update(gross_mm=round(gross, 3), litres=round(litres, 2),
                  minutes=round(litres / bp.flow_l_min, 2) if bp.flow_l_min else None,
                  remaining_depletion_mm=round(max(0, deficit - gross * bp.efficiency_pct / 100), 3))
    if bp.flow_l_min is None:
        result["warnings"].append("Pretok ni določen; časa zalivanja ni mogoče oceniti.")
    return result


def report_for(db, payload):
    bed = entity(db, Bed, payload.bed_id)
    crop = entity(db, Crop, payload.crop_id)
    cr = profile_row(db, IrrigationCropProfile, "crop_id", crop.id)
    br = profile_row(db, IrrigationBedProfile, "bed_id", bed.id)
    result = calculate(payload, bed, CropProfile.model_validate_json(cr.parameters) if cr else None,
                       BedProfile.model_validate_json(br.parameters) if br else None)
    result["crop"] = crop.name
    return result


@router.post("/calculate")
def preview(payload: DayInput, db: Session = Depends(get_db)):
    return report_for(db, payload)


@router.put("/daily")
def save_daily(payload: DayInput, db: Session = Depends(get_db)):
    report = report_for(db, payload)
    row = db.scalar(select(IrrigationDailyReport).where(IrrigationDailyReport.farm_id == FARM_ID,
                    IrrigationDailyReport.bed_id == payload.bed_id, IrrigationDailyReport.day == payload.day))
    if row is None:
        row = IrrigationDailyReport(farm_id=FARM_ID, bed_id=payload.bed_id, day=payload.day)
        db.add(row)
    report["calculated_at"] = datetime.now(timezone.utc).isoformat()
    row.report = json.dumps(report, ensure_ascii=False, allow_nan=False)
    db.commit()
    return report


@router.get("/daily")
def daily(day: date, db: Session = Depends(get_db)):
    return {"day": str(day), "automatic_execution": False, "rows": [json.loads(r.report) for r in
            db.scalars(select(IrrigationDailyReport).where(IrrigationDailyReport.farm_id == FARM_ID,
                        IrrigationDailyReport.day == day).order_by(IrrigationDailyReport.bed_id))]}


@router.get("/opensprinkler")
def opensprinkler_preview(day: date, db: Session = Depends(get_db)):
    """Produce manual HA action drafts; never call HA or mark watering as executed."""
    now = datetime.now(timezone.utc)
    mappings = {}
    for row in db.scalars(select(IrrigationBedProfile).where(IrrigationBedProfile.farm_id == FARM_ID)):
        bp = BedProfile.model_validate_json(row.parameters)
        if bp.opensprinkler_station_entity:
            mappings.setdefault(bp.opensprinkler_station_entity, []).append(row.bed_id)
    rows = []
    for row in db.scalars(select(IrrigationDailyReport).where(IrrigationDailyReport.farm_id == FARM_ID,
                          IrrigationDailyReport.day == day).order_by(IrrigationDailyReport.bed_id)):
        saved = json.loads(row.report)
        item = {"bed_id": row.bed_id, "bed": saved.get("bed"), "status": "blocked",
                "reasons": [], "action": None, "yaml": None}
        reasons = item["reasons"]
        if day != date.today():
            reasons.append("Akcija je lahko pripravljena samo za današnji dan.")
        try:
            stamp = datetime.fromisoformat(saved["calculated_at"])
            if stamp.utcoffset() is None or not timedelta(0) <= now - stamp <= timedelta(hours=6):
                reasons.append("Dnevni izračun ni svež (največ 6 ur) ali ima neveljaven čas.")
            payload = DayInput.model_validate(saved["inputs"])
            if payload.bed_id != row.bed_id or payload.day != row.day:
                raise ValueError("Posnetek se ne ujema z dnevnim zapisom.")
            current = report_for(db, payload)
            bp = BedProfile.model_validate(current.get("bed_profile", {}))
            old_bp = BedProfile.model_validate(saved.get("bed_profile", {}))
            cp = CropProfile.model_validate(current.get("crop_profile", {}))
            old_cp = CropProfile.model_validate(saved.get("crop_profile", {}))
            if bp != old_bp or cp != old_cp or current["area_m2"] != saved.get("area_m2"):
                reasons.append("Profil ali površina grede se je spremenila; ponovno izračunaj in shrani dan.")
            if current["status"] != "irrigate":
                reasons.append("Bilanca ne priporoča zalivanja ali zahteva pregled meritev.")
            station = bp.opensprinkler_station_entity
            if not station:
                reasons.append("Gredica nima povezane postaje OpenSprinkler.")
            elif len(mappings[station]) > 1:
                reasons.append("Ista postaja je povezana z več gredicami; skupne cone še niso podprte.")
            if bp.flow_l_min is None:
                reasons.append("Manjka izmerjeni pretok za to gredico.")
            seconds = math.ceil(current["litres"] / bp.flow_l_min * 60) if current["litres"] and bp.flow_l_min else 0
            if seconds <= 0:
                reasons.append("Trajanje zalivanja ni pozitivno.")
            elif seconds > bp.max_run_seconds:
                reasons.append("Trajanje presega največji čas postaje; preveri odmerek in pretok.")
            if not reasons:
                action = {"action": "opensprinkler.run_station", "target": {"entity_id": station},
                          "data": {"run_seconds": seconds, "queue_option": "append"}}
                item.update(status="draft", action=action, run_seconds=seconds, litres=current["litres"],
                            calculated_at=saved["calculated_at"], warnings=current["warnings"],
                            yaml=f"action: opensprinkler.run_station\ntarget:\n  entity_id: {station}\ndata:\n  run_seconds: {seconds}\n  queue_option: append\n")
        except (ValueError, KeyError, TypeError, HTTPException):
            reasons.append("Izračun ali profil ni več veljaven; ponovno preveri podatke in shrani dan.")
        rows.append(item)
    return {"day": str(day), "automatic_execution": False, "requires_manual_review": True,
            "rows": rows, "note": "Osnutki akcij za ročni pregled v Home Assistantu. "
            "GrowMaster ne preverja obstoja ali stanja HA postaj in ne pošilja ukazov. "
            "Pred zagonom preveri dež, tla, izbrano postajo in že izvedeno zalivanje. "
            "Akcije ne ponavljaj samodejno: ni evidence izvedbe ali zaščite pred ponovnim zagonom."}
