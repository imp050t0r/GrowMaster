"""Manual, advisory water balance. No weather polling or valve commands."""
import json
import math
import os
import re
import socket
from datetime import date, datetime, timezone, timedelta
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.ha_credentials import delete_config as delete_home_assistant_config, read_config as read_stored_home_assistant_config, write_config as write_home_assistant_config
from app.models import Bed, Crop, IrrigationBedProfile, IrrigationCropProfile, IrrigationDailyReport, IrrigationSensorGroup, IrrigationWaterLedger, Planting, Variety

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
    mode: Literal["soil_sensor", "smart_irrigation"] = "smart_irrigation"
    valve_mode: Literal["individual", "shared"] = "individual"
    irrigation_zone: str | None = Field(default=None, pattern=r"^[a-z0-9_-]{1,40}$")
    wh51_group: int | None = Field(default=None, ge=1, le=16)
    # Parse profiles saved by older GrowMaster versions; new assignments use wh51_group.
    soil_moisture_entity: str | None = Field(default=None, pattern=r"^sensor\.[a-z0-9_]+$", max_length=150, exclude=True)
    field_capacity_pct: float = Field(gt=0, le=70)
    wilting_point_pct: float = Field(ge=0, lt=70)
    efficiency_pct: float = Field(gt=0, le=100)
    flow_l_min: float | None = Field(default=None, gt=0, le=10000)
    dripline_total_length_m: float | None = Field(default=None, gt=0, le=100000)
    emitter_spacing_cm: float | None = Field(default=None, gt=0, le=500)
    emitter_flow_l_h: float | None = Field(default=None, gt=0, le=100)
    max_application_mm: float = Field(gt=0, le=100)
    sensor_dry_pct: float | None = Field(default=None, ge=0, le=100)
    sensor_wet_pct: float | None = Field(default=None, ge=0, le=100)
    source: str = Field(min_length=1, max_length=500)
    opensprinkler_station_entity: str | None = Field(default=None, pattern=r"^switch\.[a-z0-9_]+$", max_length=150)
    smart_irrigation_entity: str | None = Field(default=None, pattern=r"^sensor\.smart_irrigation_[a-z0-9_]+$", max_length=150)
    max_run_seconds: int = Field(default=3600, ge=1, le=86400)

    @model_validator(mode="after")
    def ordered(self):
        if self.wilting_point_pct >= self.field_capacity_pct:
            raise ValueError("Točka venenja mora biti manjša od poljske kapacitete.")
        if (self.sensor_dry_pct is None) != (self.sensor_wet_pct is None):
            raise ValueError("Vnesi oba umerjena praga WH51 ali nobenega.")
        if self.sensor_dry_pct is not None and self.sensor_dry_pct >= self.sensor_wet_pct:
            raise ValueError("Suhi prag WH51 mora biti manjši od mokrega.")
        dripline_inputs = (self.dripline_total_length_m, self.emitter_spacing_cm, self.emitter_flow_l_h)
        if any(value is not None for value in dripline_inputs):
            if any(value is None for value in dripline_inputs):
                raise ValueError("Za izračun pretoka vnesi skupno dolžino cevi, razmik in pretok kapljača.")
            # Input length is the sum of all dripline laterals on this bed.
            emitter_count = self.dripline_total_length_m / (self.emitter_spacing_cm / 100)
            calculated_flow = emitter_count * self.emitter_flow_l_h / 60
            if not math.isfinite(calculated_flow) or calculated_flow <= 0 or calculated_flow > 10000:
                raise ValueError("Izračunani skupni pretok je zunaj dovoljenega območja.")
            self.flow_l_min = calculated_flow
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
            raise ValueError("Meritev vlage v tleh zahteva tudi čas meritve.")
        if self.sensor_observed_at is not None and self.sensor_observed_at.utcoffset() is None:
            raise ValueError("Čas meritve mora vsebovati časovni pas.")
        return self


class WaterLedgerInput(Input):
    bed_id: int = Field(gt=0)
    day: date
    opening_depletion_mm: float = Field(ge=0, le=2100)
    etc_mm: float = Field(ge=0, le=30)
    effective_rain_mm: float = Field(ge=0, le=500)
    applied_irrigation_mm: float = Field(ge=0, le=100)
    source: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def day_not_future(self):
        if self.day > date.today():
            raise ValueError("Vodna bilanca ne more biti v prihodnosti.")
        return self


class SensorGroupInput(Input):
    name: str = Field(min_length=1, max_length=80)
    entity_id: str | None = Field(default=None, pattern=r"^sensor\.[a-z0-9_]+$", max_length=150)


class HomeAssistantConfigInput(Input):
    url: str = Field(min_length=8, max_length=2048)
    token: SecretStr | None = None

    @model_validator(mode="after")
    def valid_url(self):
        parsed = urlparse(self.url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Vnesi veljaven http(s) URL Home Assistanta brez prijavnih podatkov, poizvedbe ali fragmenta.")
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("URL Home Assistanta vsebuje neveljavna vrata.") from exc
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
                     db.scalars(select(IrrigationBedProfile).where(IrrigationBedProfile.farm_id == FARM_ID))],
            "sensor_groups": [{"group_number": row.group_number, "name": row.name, "entity_id": row.entity_id}
                              for row in db.scalars(select(IrrigationSensorGroup).where(IrrigationSensorGroup.farm_id == FARM_ID).order_by(IrrigationSensorGroup.group_number))]}


@router.put("/sensor-groups/{group_number}")
def save_sensor_group(group_number: int, payload: SensorGroupInput, db: Session = Depends(get_db)):
    if not 1 <= group_number <= 16:
        raise HTTPException(422, "WH51 skupina mora biti med 1 in 16.")
    row = db.scalar(select(IrrigationSensorGroup).where(IrrigationSensorGroup.farm_id == FARM_ID,
                                                         IrrigationSensorGroup.group_number == group_number))
    if row is None:
        row = IrrigationSensorGroup(farm_id=FARM_ID, group_number=group_number)
        db.add(row)
    row.name, row.entity_id = payload.name, payload.entity_id
    db.commit()
    return {"group_number": group_number, **payload.model_dump()}


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


def apply_wh51_reading(db, payload: DayInput, report: dict):
    """Use the configured group sensor as the soil reading for this bed."""
    bed_profile_row = profile_row(db, IrrigationBedProfile, "bed_id", payload.bed_id)
    if not bed_profile_row:
        return report
    bed_profile = BedProfile.model_validate_json(bed_profile_row.parameters)
    if bed_profile.mode != "soil_sensor":
        return report
    if not bed_profile.wh51_group:
        report.update(status="review", confidence="low")
        report["warnings"].append("Gredici ni dodeljena WH51 skupina.")
        return report
    group = db.scalar(select(IrrigationSensorGroup).where(
        IrrigationSensorGroup.farm_id == FARM_ID, IrrigationSensorGroup.group_number == bed_profile.wh51_group))
    if not group or not group.entity_id:
        report.update(status="review", confidence="low")
        report["warnings"].append("Izbrani WH51 skupini manjka entity ID.")
        return report
    base_url, token = home_assistant_config()
    if not base_url:
        report.update(status="review", confidence="low")
        report["warnings"].append("Home Assistant ni nastavljen; meritve WH51 ni mogoče prebrati.")
        return report
    try:
        with httpx.Client(timeout=5.0, follow_redirects=False) as client:
            response = client.get(f"{base_url}/api/states/{group.entity_id}", headers=ha_headers(token))
        if response.status_code != 200:
            raise ValueError("WH51 entity ni dosegljiv.")
        data = response.json()
        value = float(data["state"])
        if not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError("WH51 vrednost ni v območju 0–100 %.")
        if data.get("attributes", {}).get("unit_of_measurement") != "%":
            raise ValueError("WH51 entity nima enote %.")
        observed_at = datetime.fromisoformat(data["last_updated"])
        age = (datetime.now(timezone.utc) - observed_at.astimezone(timezone.utc)).total_seconds()
        if not 0 <= age <= 6 * 3600:
            raise ValueError("WH51 meritev ni sveža (največ 6 ur).")
        report.setdefault("inputs", {})["soil_moisture_pct"] = value
        report["inputs"]["sensor_observed_at"] = observed_at.isoformat()
        report["wh51"] = {"group_number": group.group_number, "group_name": group.name,
                          "entity_id": group.entity_id, "value_pct": value,
                          "observed_at": observed_at.isoformat(), "age_seconds": round(age)}
        if bed_profile.sensor_dry_pct is None or bed_profile.sensor_wet_pct is None:
            report.update(status="review", confidence="low")
            report["warnings"].append("WH51 pragova suho/mokro še nisi umeril za to gredico.")
        else:
            should_irrigate = report.get("status") == "irrigate"
            if (should_irrigate and value >= bed_profile.sensor_wet_pct) or (not should_irrigate and value <= bed_profile.sensor_dry_pct):
                report.update(status="review", confidence="low")
                report["warnings"].append("WH51 in vodna bilanca se ne ujemata; preveri stanje grede.")
            else:
                report["warnings"].append("Bilanca preverjena s skupno meritvijo WH51; senzor predstavlja več gredic v skupini.")
    except (httpx.RequestError, ValueError, KeyError, TypeError) as exc:
        report.update(status="review", confidence="low")
        report["warnings"].append(f"Meritve WH51 ni mogoče varno uporabiti: {exc}")
    return report


@router.post("/calculate")
def preview(payload: DayInput, db: Session = Depends(get_db)):
    return apply_wh51_reading(db, payload, report_for(db, payload))


@router.put("/daily")
def save_daily(payload: DayInput, db: Session = Depends(get_db)):
    report = apply_wh51_reading(db, payload, report_for(db, payload))
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


@router.get("/water-ledger")
def water_ledger(bed_id: int, through: date, db: Session = Depends(get_db)):
    entity(db, Bed, bed_id)
    entries = db.scalars(select(IrrigationWaterLedger).where(
        IrrigationWaterLedger.farm_id == FARM_ID, IrrigationWaterLedger.bed_id == bed_id,
        IrrigationWaterLedger.day <= through).order_by(IrrigationWaterLedger.day.desc()).limit(30))
    rows = [{"day": str(row.day), "opening_depletion_mm": row.opening_depletion_mm,
             "etc_mm": row.etc_mm, "effective_rain_mm": row.effective_rain_mm,
             "applied_irrigation_mm": row.applied_irrigation_mm,
             "closing_depletion_mm": row.closing_depletion_mm, "source": row.source}
            for row in entries]
    return {"bed_id": bed_id, "through": str(through), "rows": list(reversed(rows))}


@router.put("/water-ledger")
def save_water_ledger(payload: WaterLedgerInput, db: Session = Depends(get_db)):
    entity(db, Bed, payload.bed_id)
    previous = db.scalar(select(IrrigationWaterLedger).where(
        IrrigationWaterLedger.farm_id == FARM_ID, IrrigationWaterLedger.bed_id == payload.bed_id,
        IrrigationWaterLedger.day < payload.day).order_by(IrrigationWaterLedger.day.desc()).limit(1))
    existing = db.scalar(select(IrrigationWaterLedger).where(
        IrrigationWaterLedger.farm_id == FARM_ID, IrrigationWaterLedger.bed_id == payload.bed_id,
        IrrigationWaterLedger.day == payload.day))
    if previous and payload.opening_depletion_mm != previous.closing_depletion_mm:
        raise HTTPException(409, "Začetni primanjkljaj se ne ujema s končnim stanjem zadnjega shranjenega dne.")
    if existing and db.scalar(select(IrrigationWaterLedger.id).where(
        IrrigationWaterLedger.farm_id == FARM_ID, IrrigationWaterLedger.bed_id == payload.bed_id,
        IrrigationWaterLedger.day > payload.day).limit(1)):
        raise HTTPException(409, "Popravek starejšega dne bi spremenil poznejšo bilanco; najprej popravi naslednje dni po vrsti.")
    current_report = db.scalar(select(IrrigationDailyReport).where(
        IrrigationDailyReport.farm_id == FARM_ID, IrrigationDailyReport.bed_id == payload.bed_id,
        IrrigationDailyReport.day == payload.day))
    if not current_report:
        raise HTTPException(409, "Najprej izračunaj in shrani dnevno bilanco za to gredico.")
    report = json.loads(current_report.report)
    if report.get("etc_mm") is None:
        raise HTTPException(409, "Dnevni izračun nima ETc.")
    if not math.isclose(payload.etc_mm, float(report["etc_mm"]), rel_tol=0, abs_tol=0.001):
        raise HTTPException(409, "ETc se ne ujema s shranjenim dnevnim izračunom; ponovno izračunaj dan.")
    profile = profile_row(db, IrrigationBedProfile, "bed_id", payload.bed_id)
    if not profile:
        raise HTTPException(409, "Manjka profil grede.")
    bed_profile = BedProfile.model_validate_json(profile.parameters)
    raw_closing = payload.opening_depletion_mm + float(report["etc_mm"]) - payload.effective_rain_mm - payload.applied_irrigation_mm * bed_profile.efficiency_pct / 100
    capacity = report.get("taw_mm")
    if capacity is None:
        raise HTTPException(409, "Dnevni izračun nima veljavne kapacitete korenin.")
    closing = round(min(capacity, max(0, raw_closing)), 3)
    row = existing or IrrigationWaterLedger(farm_id=FARM_ID, bed_id=payload.bed_id, day=payload.day)
    row.opening_depletion_mm = payload.opening_depletion_mm
    row.etc_mm = payload.etc_mm
    row.effective_rain_mm = payload.effective_rain_mm
    row.applied_irrigation_mm = payload.applied_irrigation_mm
    row.closing_depletion_mm = closing
    row.source = payload.source
    db.add(row)
    db.commit()
    return {"bed_id": payload.bed_id, "day": str(payload.day),
            "opening_depletion_mm": payload.opening_depletion_mm, "closing_depletion_mm": closing,
            "capacity_mm": capacity, "saved": True,
            "warning": "To potrdiš samo po preverbi dejanskega dežja in izvedenega zalivanja."}


@router.get("/daily-readiness")
def daily_readiness(day: date, db: Session = Depends(get_db)):
    """Summarize every active bed and identify missing data before any HA write."""
    beds = list(db.scalars(select(Bed).where(Bed.farm_id == FARM_ID).order_by(Bed.name)))
    crop_profiles = {row.crop_id for row in db.scalars(select(IrrigationCropProfile).where(IrrigationCropProfile.farm_id == FARM_ID))}
    bed_profiles = {row.bed_id: BedProfile.model_validate_json(row.parameters) for row in
                    db.scalars(select(IrrigationBedProfile).where(IrrigationBedProfile.farm_id == FARM_ID))}
    station_beds = {}
    for bed_id, bed_profile in bed_profiles.items():
        if bed_profile.opensprinkler_station_entity:
            station_beds.setdefault(bed_profile.opensprinkler_station_entity, []).append((bed_id, bed_profile))
    sensor_groups = {row.group_number: row for row in db.scalars(select(IrrigationSensorGroup).where(IrrigationSensorGroup.farm_id == FARM_ID))}
    used_groups = {profile.wh51_group for profile in bed_profiles.values()
                   if profile.mode == "soil_sensor" and profile.wh51_group is not None}
    reports = {row.bed_id: json.loads(row.report) for row in db.scalars(
        select(IrrigationDailyReport).where(IrrigationDailyReport.farm_id == FARM_ID, IrrigationDailyReport.day == day))}
    rows = []
    active = db.scalars(select(Planting).where(Planting.farm_id == FARM_ID, Planting.status == "active")
                        .order_by(Planting.created_at.desc())).all()
    latest_by_bed = {}
    for planting in active:
        latest_by_bed.setdefault(planting.bed_id, planting)
    ha_state_cache = {}
    for bed in beds:
        planting = latest_by_bed.get(bed.id)
        if planting is None:
            continue
        profile = bed_profiles.get(bed.id)
        report = reports.get(bed.id)
        reasons = []
        if planting.crop_id not in crop_profiles:
            reasons.append("Manjka profil trenutne kulture.")
        if profile is None:
            reasons.append("Manjka profil grede.")
        if profile and profile.mode == "smart_irrigation" and not profile.smart_irrigation_entity:
            reasons.append("Manjka Smart Irrigation cona.")
        if profile and profile.mode == "soil_sensor" and not profile.irrigation_zone:
            reasons.append("Izbran je način s senzorjem vlage, vendar namakalna cona ni nastavljena.")
        sensor_group = sensor_groups.get(profile.wh51_group) if profile and profile.wh51_group else None
        if profile and profile.mode == "soil_sensor" and not profile.wh51_group:
            reasons.append("Gredici še ni ročno dodeljena WH51 skupina.")
        if profile and profile.mode == "soil_sensor" and profile.wh51_group and (not sensor_group or not sensor_group.entity_id):
            reasons.append("Izbrani WH51 skupini manjka Home Assistant entity ID.")
        if profile and profile.mode == "soil_sensor" and not profile.smart_irrigation_entity:
            reasons.append("Za način s senzorjem vlage še vedno manjka Smart Irrigation cona za upravljanje urnika.")
        if report is None:
            if profile is None or profile.mode != "smart_irrigation" or not profile.smart_irrigation_entity:
                reasons.append("Za izbrani dan še ni shranjenega izračuna.")
            report_status = "missing_data"
            calculated_at = None
        else:
            report_status = report.get("status", "missing_data")
            calculated_at = report.get("calculated_at")
            if report_status in {"review", "missing_data"}:
                reasons.append("Dnevni izračun zahteva podatke ali pregled.")
            try:
                stamp = datetime.fromisoformat(calculated_at)
                if day != date.today() or stamp.utcoffset() is None or not timedelta(0) <= datetime.now(timezone.utc) - stamp <= timedelta(hours=6):
                    reasons.append("Dnevni izračun ni današnji ali je starejši od šestih ur.")
            except (TypeError, ValueError):
                reasons.append("Čas dnevnega izračuna manjka ali ni veljaven.")
            if report.get("crop_id") != planting.crop_id:
                reasons.append("Izračun ne ustreza trenutni aktivni kulturi na gredici.")
        if profile and profile.mode == "soil_sensor" and sensor_group and sensor_group.entity_id:
            sensor_state = None
            base_url, token = home_assistant_config()
            if not base_url:
                reasons.append("Povezava Home Assistant ni nastavljena za preverjanje senzorja vlage.")
            else:
                try:
                    if sensor_group.entity_id not in ha_state_cache:
                        with httpx.Client(timeout=5.0, follow_redirects=False) as client:
                            sensor_response = client.get(f"{base_url}/api/states/{sensor_group.entity_id}", headers=ha_headers(token))
                        ha_state_cache[sensor_group.entity_id] = (sensor_response.status_code, sensor_response.json() if sensor_response.status_code == 200 else None)
                    sensor_status, sensor_data = ha_state_cache[sensor_group.entity_id]
                    if sensor_status == 200:
                        sensor_state = sensor_data.get("state")
                        sensor_time = datetime.fromisoformat(sensor_data["last_updated"])
                        if sensor_state in {None, "unknown", "unavailable"} or not 0 <= (datetime.now(timezone.utc) - sensor_time.astimezone(timezone.utc)).total_seconds() <= 6 * 3600:
                            reasons.append("Senzor vlage je nedosegljiv ali starejši od šestih ur.")
                        elif sensor_data.get("attributes", {}).get("unit_of_measurement") != "%":
                            reasons.append("WH51 entity nima pričakovane enote %.")
                        elif profile.sensor_dry_pct is None or profile.sensor_wet_pct is None:
                            reasons.append("Za to gredico nista umerjena suhi in mokri prag WH51.")
                        elif report:
                            try:
                                moisture = float(sensor_state)
                                expected_irrigation = report.get("status") == "irrigate"
                                disagreement = ((expected_irrigation and moisture >= profile.sensor_wet_pct) or
                                                (not expected_irrigation and moisture <= profile.sensor_dry_pct))
                                if disagreement:
                                    reasons.append("Sveži WH51 in shranjena vodna bilanca se ne ujemata.")
                            except (TypeError, ValueError):
                                reasons.append("WH51 stanje ni številski odstotek vlage.")
                    else:
                        reasons.append("Senzor vlage ni bil najden ali HA ni vrnil meritve.")
                except (httpx.RequestError, ValueError, KeyError, TypeError):
                    reasons.append("Senzor vlage trenutno ni preverljiv prek Home Assistanta.")
            if report and report.get("inputs", {}).get("soil_moisture_pct") is None:
                reasons.append("Dnevni izračun v načinu s senzorjem nima shranjene meritve vlage.")
        smart_irrigation_seconds = None
        smart_action = None
        if profile and profile.mode == "smart_irrigation" and profile.smart_irrigation_entity:
            base_url, token = home_assistant_config()
            if not base_url:
                reasons.append("Home Assistant ni nastavljen za branje trajanja Smart Irrigation cone.")
            else:
                try:
                    if profile.smart_irrigation_entity not in ha_state_cache:
                        with httpx.Client(timeout=5.0, follow_redirects=False) as client:
                            si_response = client.get(f"{base_url}/api/states/{profile.smart_irrigation_entity}", headers=ha_headers(token))
                        ha_state_cache[profile.smart_irrigation_entity] = (si_response.status_code, si_response.json() if si_response.status_code == 200 else None)
                    si_status, si_data = ha_state_cache[profile.smart_irrigation_entity]
                    if si_status != 200:
                        reasons.append("Smart Irrigation entity ni dosegljiv v Home Assistantu.")
                    else:
                        smart_irrigation_seconds = float(si_data.get("state"))
                        si_updated = datetime.fromisoformat(si_data.get("attributes", {}).get("last_calculated") or si_data["last_updated"])
                        si_age = (datetime.now(timezone.utc) - si_updated.astimezone(timezone.utc)).total_seconds()
                        if not math.isfinite(smart_irrigation_seconds) or smart_irrigation_seconds < 0:
                            raise ValueError("Trajanje ni veljavno nenegativno število.")
                        if si_data.get("attributes", {}).get("unit_of_measurement") != "seconds":
                            raise ValueError("Smart Irrigation trajanje nima enote seconds.")
                        if not 0 <= si_age <= 6 * 3600:
                            reasons.append("Smart Irrigation izračun je starejši od šestih ur.")
                except (httpx.RequestError, ValueError, KeyError, TypeError):
                    smart_irrigation_seconds = None
                    reasons.append("Trajanja Smart Irrigation ni mogoče varno prebrati.")
        # The valve belongs permanently to the bed. A crop change affects its
        # water calculation, never the bed-to-valve mapping.
        if profile and profile.mode == "smart_irrigation" and smart_irrigation_seconds is not None and smart_irrigation_seconds > 0:
            station = profile.opensprinkler_station_entity
            if not station:
                reasons.append("Zalivanje je priporočeno, vendar gredica nima povezane OpenSprinkler postaje.")
            elif len(station_beds.get(station, [])) > 1 and (profile.valve_mode != "shared" or any(peer.valve_mode != "shared" for _, peer in station_beds[station])):
                reasons.append("Isti ventil je na več gredicah označen kot individualen; izberi skupni ventil za vse te gredice.")
            elif smart_irrigation_seconds > profile.max_run_seconds:
                reasons.append("Smart Irrigation trajanje presega omejitev postaje.")
            else:
                smart_action = {"action": "opensprinkler.run_station", "target": {"entity_id": station},
                                "data": {"run_seconds": math.ceil(smart_irrigation_seconds), "queue_option": "append"}}
        elif profile and profile.mode == "soil_sensor" and report and report_status == "irrigate":
            station = profile.opensprinkler_station_entity
            if not station:
                reasons.append("Zalivanje je priporočeno, vendar gredica nima povezane OpenSprinkler postaje.")
            elif len(station_beds.get(station, [])) > 1 and (profile.valve_mode != "shared" or any(peer.valve_mode != "shared" for _, peer in station_beds[station])):
                reasons.append("Isti ventil je na več gredicah označen kot individualen; izberi skupni ventil za vse te gredice.")
            elif profile.flow_l_min is None:
                reasons.append("Manjka izmerjeni pretok te gredice za izračun trajanja ventila.")
            else:
                litres = report.get("litres")
                if litres is None or not math.isfinite(float(litres)) or float(litres) <= 0:
                    reasons.append("Izračun ne vsebuje veljavnega pozitivnega odmerka vode.")
                else:
                    run_seconds = math.ceil(float(litres) / profile.flow_l_min * 60)
                    if run_seconds > profile.max_run_seconds:
                        reasons.append("Izračunano trajanje presega omejitev ventila.")
                    else:
                        smart_action = {"action": "opensprinkler.run_station", "target": {"entity_id": station},
                                        "data": {"run_seconds": run_seconds, "queue_option": "append"}}
        if reasons:
            smart_action = None
        smart_irrigation_litres = (
            round(profile.flow_l_min * smart_irrigation_seconds / 60, 2)
            if profile and profile.flow_l_min is not None and smart_irrigation_seconds is not None
            else None
        )
        days_after_sowing = (day - planting.sowing_date).days
        suggested_stage = "initial" if days_after_sowing < 20 else "mid"
        row_data = {"bed_id": bed.id, "bed": bed.name, "area_m2": bed.area_m2,
                     "crop_id": planting.crop_id, "crop": planting.crop.name,
                     "variety": planting.variety.name if planting.variety else None,
                     "sowing_date": str(planting.sowing_date), "days_after_sowing": days_after_sowing,
                     "suggested_stage": suggested_stage, "stage_requires_confirmation": True,
                     "planting_id": planting.id, "zone_entity": profile.smart_irrigation_entity if profile else None,
                     "mode": profile.mode if profile else None,
                     "wh51_group": profile.wh51_group if profile else None,
                     "wh51_group_name": sensor_group.name if sensor_group else None,
                     "sensor_group_beds": sum(1 for other in bed_profiles.values() if other.mode == "soil_sensor" and other.wh51_group == (profile.wh51_group if profile else None)) if profile and profile.wh51_group else 0,
                     "smart_irrigation_seconds": smart_irrigation_seconds,
                     "estimated_litres": smart_irrigation_litres,
                     "action": smart_action,
                     "decision": (("irrigate" if report_status == "irrigate" else "hold" if report_status == "hold" else "review")
                                  if profile and profile.mode == "soil_sensor" else
                                  "irrigate" if smart_irrigation_seconds and smart_irrigation_seconds > 0 else
                                  "hold" if smart_irrigation_seconds == 0 else "review"),
                     "irrigation_zone": profile.irrigation_zone if profile else None,
                     "report_status": report_status, "calculated_at": calculated_at,
                     "ready": not reasons, "reasons": reasons}
        if profile and profile.opensprinkler_station_entity and profile.valve_mode == "shared" and len(station_beds.get(profile.opensprinkler_station_entity, [])) > 1:
            row_data["_shared_candidate"] = smart_action
        rows.append(row_data)
    valve_groups = []
    for station, members in station_beds.items():
        if len(members) < 2 or not all(member.valve_mode == "shared" for _, member in members):
            continue
        bed_ids = sorted(member_id for member_id, _ in members)
        group_rows = [row for row in rows if row["bed_id"] in bed_ids]
        reasons = []
        if len(group_rows) != len(bed_ids):
            reasons.append("Vse gredice, priključene na skupni ventil, morajo imeti aktivno zasaditev.")
        if any(not row["ready"] or row["decision"] != "irrigate" or not row.get("_shared_candidate") for row in group_rows):
            reasons.append("Vsaka gredica na skupnem ventilu mora imeti svež izračun, ki priporoča zalivanje.")
        safe_limits = []
        group_flows = []
        for member_id, member in members:
            report = reports.get(member_id)
            bed = next((item for item in beds if item.id == member_id), None)
            if report is None or bed is None or member.flow_l_min is None:
                reasons.append("Za vsako gredico skupine sta potrebna današnji izračun in izmerjeni pretok.")
                continue
            depletion = report.get("depletion_mm")
            if depletion is None or not math.isfinite(float(depletion)):
                reasons.append("Vodna bilanca skupne gredice nima veljavnega primanjkljaja.")
                continue
            # Bound the shared run by the least water any member can safely accept.
            safe_depth = min(member.max_application_mm, float(depletion) / (member.efficiency_pct / 100))
            safe_limits.append(min(member.max_run_seconds, math.floor(safe_depth * bed.area_m2 / member.flow_l_min * 60)))
            group_flows.append((member_id, member.flow_l_min))
        requested = [row["_shared_candidate"]["data"]["run_seconds"] for row in group_rows if row.get("_shared_candidate")]
        run_seconds = max(requested) if requested else 0
        if safe_limits and run_seconds > min(safe_limits):
            reasons.append("Skupni čas bi presegel varen odmerek vsaj za eno gredico.")
        action = None
        if not reasons and run_seconds > 0:
            action = {"action": "opensprinkler.run_station", "target": {"entity_id": station},
                      "data": {"run_seconds": run_seconds, "queue_option": "append"}}
        bed_water_estimates = ([{"bed_id": member_id, "litres": round(flow_l_min * run_seconds / 60, 1)}
                                for member_id, flow_l_min in group_flows] if action else [])
        estimated_litres = round(sum(item["litres"] for item in bed_water_estimates), 1) if action else None
        for row in group_rows:
            row.pop("_shared_candidate", None)
            row["action"] = None
            if reasons:
                row["ready"] = False
                row["reasons"].extend(reason for reason in reasons if reason not in row["reasons"])
        valve_groups.append({"station": station, "bed_ids": bed_ids, "status": "draft" if action else "blocked",
                             "action": action, "run_seconds": run_seconds if action else None,
                             "estimated_litres": estimated_litres, "bed_water_estimates": bed_water_estimates,
                             "reasons": reasons})
    for row in rows:
        row.pop("_shared_candidate", None)
    return {"day": str(day), "active_beds": len(rows), "ready_beds": sum(row["ready"] for row in rows),
            "needs_attention": sum(not row["ready"] for row in rows), "automatic_execution": False,
            "rows": rows, "valve_groups": valve_groups,
            "note": "Pregled vseh aktivnih gredic. Ne izračuna ET₀, ne pošlje podatkov v Home Assistant in ne zažene ventilov."}


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


@router.get("/smart-irrigation")
def smart_irrigation_preview(day: date, db: Session = Depends(get_db)):
    """Draft current-crop Kc updates; never calculate or start a run."""
    beds = {bed.id: bed for bed in db.scalars(select(Bed).where(Bed.farm_id == FARM_ID))}
    crop_profiles = {row.crop_id: CropProfile.model_validate_json(row.parameters) for row in
                     db.scalars(select(IrrigationCropProfile).where(IrrigationCropProfile.farm_id == FARM_ID))}
    bed_profiles = {row.bed_id: BedProfile.model_validate_json(row.parameters) for row in
                    db.scalars(select(IrrigationBedProfile).where(IrrigationBedProfile.farm_id == FARM_ID))}
    mapped_zones = {}
    for bed_id, profile in bed_profiles.items():
        if profile.smart_irrigation_entity:
            mapped_zones.setdefault(profile.smart_irrigation_entity, []).append(bed_id)

    active_plantings = db.scalars(
        select(Planting).where(Planting.farm_id == FARM_ID, Planting.status == "active")
        .order_by(Planting.created_at.desc())
    ).all()
    latest_by_bed = {}
    for planting in active_plantings:
        latest_by_bed.setdefault(planting.bed_id, planting)

    rows = []
    for bed_id, planting in latest_by_bed.items():
        bed = beds.get(bed_id)
        profile = bed_profiles.get(bed_id)
        crop_profile = crop_profiles.get(planting.crop_id)
        item = {
            "bed_id": bed_id, "bed": bed.name if bed else None,
            "crop_id": planting.crop_id, "crop": planting.crop.name,
            "variety": planting.variety.name if planting.variety else None,
            "sowing_date": str(planting.sowing_date), "status": "blocked",
            "stage": None, "stage_requires_confirmation": True,
            "multiplier": None, "action": None, "yaml": None, "reasons": [],
        }
        reasons = item["reasons"]
        days_after_sowing = (day - planting.sowing_date).days
        item["days_after_sowing"] = days_after_sowing
        # This is only a starting suggestion. Crop-specific growth stages must be
        # checked by the user before sending the Kc update to Home Assistant.
        stage = "initial" if days_after_sowing < 20 else "mid"
        item["stage"] = stage
        if day != date.today():
            reasons.append("Kc lahko pripraviš samo za današnji pregled.")
        if days_after_sowing < 0:
            reasons.append("Datum setve je po izbranem dnevu; preveri zasaditev.")
        if bed is None or profile is None or crop_profile is None:
            reasons.append("Manjka gredica, profil grede ali profil aktivne kulture.")
        zone_entity = profile.smart_irrigation_entity if profile else None
        if profile and profile.mode != "smart_irrigation":
            reasons.append("Gredica je nastavljena na način s talnim senzorjem.")
        if not zone_entity:
            reasons.append("Gredica nima povezane Smart Irrigation cone.")
        elif len(mapped_zones.get(zone_entity, [])) > 1:
            reasons.append("Ista Smart Irrigation cona je povezana z več gredicami; Kc mora biti določen enkrat na cono.")
        multiplier = getattr(crop_profile, "kc_" + stage) if crop_profile else None
        if multiplier is None or not math.isfinite(multiplier) or not 0 <= multiplier <= 2:
            reasons.append("Koeficient Kc ni veljaven.")
        if not reasons:
            action = {
                "action": "smart_irrigation.set_multiplier",
                "target": {"entity_id": zone_entity},
                "data": {"new_multiplier_value": multiplier},
            }
            item.update(
                status="draft", action=action, multiplier=multiplier,
                yaml=("action: smart_irrigation.set_multiplier\n"
                      f"target:\n  entity_id: {zone_entity}\n"
                      f"data:\n  new_multiplier_value: {multiplier}\n"),
            )
        rows.append(item)

    return {
        "day": str(day), "automatic_execution": False, "requires_manual_review": True,
        "rows": rows,
        "note": "Osnutki Kc izhajajo iz trenutno aktivne kulture in profila kulture, ne iz shranjenega dnevnega izračuna. "
                "Faza je samo predlog po dnevih od setve; pred pošiljanjem preveri dejansko fazo in Kc. "
                "Pošlje se samo Kc. GrowMaster ne izračuna časa in ne sproži namakanja.",
    }

def home_assistant_config():
    """Read the encrypted per-installation setting, with environment fallback."""
    try:
        stored = read_stored_home_assistant_config()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    base_url = (stored["url"] if stored else os.environ.get("HOME_ASSISTANT_URL", "")).strip().rstrip("/")
    token = (stored["token"] if stored else os.environ.get("HOME_ASSISTANT_TOKEN", "")).strip()
    parsed = urlparse(base_url)
    if not base_url or not token:
        return None, None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise HTTPException(503, "HOME_ASSISTANT_URL mora biti veljaven http(s) naslov brez uporabniškega imena ali gesla.")
    if parsed.hostname and parsed.hostname.lower().endswith(".local"):
        try:
            socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise HTTPException(503, "Ime Home Assistanta .local ni razrešljivo iz GrowMaster backend vsebnika; uporabi LAN IP naslov.") from exc
    return base_url, token


def ha_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@router.get("/home-assistant/status")
def home_assistant_status():
    """Expose the non-secret URL and credential state, never the token."""
    try:
        stored = read_stored_home_assistant_config()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    base_url = (stored["url"] if stored else os.environ.get("HOME_ASSISTANT_URL", "")).strip().rstrip("/")
    token = (stored["token"] if stored else os.environ.get("HOME_ASSISTANT_TOKEN", "")).strip()
    return {"configured": bool(base_url and token), "url": base_url or "", "token_configured": bool(token),
            "source": "application" if stored else "environment", "automatic_execution": False,
            "note": "Žeton je shranjen šifrirano na strežniku GrowMaster; API ga nikoli ne vrne."}


@router.put("/home-assistant/config")
def save_home_assistant_config(payload: HomeAssistantConfigInput):
    """Save Home Assistant credentials encrypted in the persistent data volume."""
    try:
        current = read_stored_home_assistant_config()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    submitted_token = payload.token.get_secret_value().strip() if payload.token else ""
    if len(submitted_token) > 8192:
        raise HTTPException(422, "Dolgoročni žeton je predolg.")
    token = submitted_token or (
        current["token"] if current else os.environ.get("HOME_ASSISTANT_TOKEN", "").strip()
    )
    if not token:
        raise HTTPException(422, "Vnesi dolgoročni dostopni žeton Home Assistanta.")
    url = payload.url.strip().rstrip("/")
    try:
        write_home_assistant_config(url, token)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(503, "Nastavitve Home Assistanta ni mogoče varno shraniti na podatkovni disk GrowMasterja.") from exc
    return {"configured": True, "url": url, "token_configured": True, "source": "application",
            "message": "Povezava Home Assistanta je shranjena. Žeton ni prikazan."}


@router.delete("/home-assistant/config")
def clear_home_assistant_config():
    """Remove the app-managed credential file; never return a secret."""
    try:
        deleted = delete_home_assistant_config()
    except OSError as exc:
        raise HTTPException(503, "Nastavitve Home Assistanta ni mogoče izbrisati.") from exc
    status = home_assistant_status()
    base_url = status["url"] if status["configured"] else ""
    return {"deleted": deleted, "configured": bool(base_url), "url": base_url or "",
            "token_configured": bool(base_url), "source": "environment" if base_url else None,
            "message": "Nastavitev iz aplikacije je izbrisana."}


@router.post("/home-assistant/test")
def home_assistant_test():
    """Check the HA API without changing entities or starting irrigation."""
    base_url, token = home_assistant_config()
    if not base_url:
        raise HTTPException(503, "Nastavi HOME_ASSISTANT_URL in HOME_ASSISTANT_TOKEN na strežniku GrowMaster.")
    try:
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            response = client.get(f"{base_url}/api/", headers=ha_headers(token))
    except httpx.RequestError as exc:
        raise HTTPException(502, "Home Assistant ni dosegljiv iz strežnika GrowMaster.") from exc
    if response.status_code == 401:
        raise HTTPException(502, "Home Assistant je dosegljiv, vendar žeton ni veljaven.")
    if response.status_code != 200:
        raise HTTPException(502, f"Home Assistant API je vrnil HTTP {response.status_code}.")
    try:
        info = response.json()
    except ValueError as exc:
        raise HTTPException(502, "Home Assistant API ni vrnil veljavnega odgovora.") from exc
    return {"connected": True, "message": info.get("message", "API dosegljiv"), "automatic_execution": False}


@router.get("/home-assistant/states")
def home_assistant_states(db: Session = Depends(get_db)):
    """Read configured weather and soil sensor states without triggering actions."""
    base_url, token = home_assistant_config()
    if not base_url:
        raise HTTPException(503, "Nastavi HOME_ASSISTANT_URL in HOME_ASSISTANT_TOKEN na strežniku GrowMaster.")
    entities = set()
    groups = list(db.scalars(select(IrrigationSensorGroup).where(IrrigationSensorGroup.farm_id == FARM_ID)))
    for group in groups:
        if group.entity_id:
            entities.add(group.entity_id)
    # Weather sensor entities are provided explicitly through the environment so no
    # assumptions are made about Ecowitt naming or sensor models.
    weather_entities = [item.strip() for item in os.environ.get("HOME_ASSISTANT_WEATHER_ENTITIES", "").split(",") if item.strip()]
    for entity_id in weather_entities:
        if not re.fullmatch(r"sensor\.[a-z0-9_]+", entity_id):
            raise HTTPException(503, "HOME_ASSISTANT_WEATHER_ENTITIES vsebuje neveljaven sensor entity ID.")
        entities.add(entity_id)
    try:
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            result = []
            for entity_id in sorted(entities):
                response = client.get(f"{base_url}/api/states/{entity_id}", headers=ha_headers(token))
                if response.status_code == 401:
                    raise HTTPException(502, "Home Assistant je zavrnil žeton.")
                if response.status_code == 404:
                    result.append({"entity_id": entity_id, "available": False, "error": "Entity ni najden."})
                    continue
                if response.status_code != 200:
                    raise HTTPException(502, f"Home Assistant je vrnil HTTP {response.status_code} pri branju entity-ja.")
                data = response.json()
                state = data.get("state")
                attributes = data.get("attributes", {})
                try:
                    numeric_state = float(state)
                    numeric_valid = math.isfinite(numeric_state)
                except (ValueError, TypeError):
                    numeric_state, numeric_valid = None, False
                updated = data.get("last_updated")
                try:
                    updated_at = datetime.fromisoformat(updated)
                    age_seconds = (datetime.now(timezone.utc) - updated_at.astimezone(timezone.utc)).total_seconds()
                    fresh = 0 <= age_seconds <= 6 * 3600
                except (ValueError, TypeError, AttributeError):
                    age_seconds, fresh = None, False
                issue = None
                if state in {None, "unknown", "unavailable"}:
                    issue = "Entity nima dosegljive vrednosti."
                elif not numeric_valid:
                    issue = "Vrednost ni končno število."
                elif not fresh:
                    issue = "Vrednost ni sveža (največ 6 ur) ali nima veljavnega časa."
                result.append({"entity_id": entity_id, "available": issue is None,
                               "numeric_value": numeric_state, "state": state,
                               "unit": attributes.get("unit_of_measurement"), "attributes": attributes,
                               "last_changed": data.get("last_changed"), "last_updated": updated,
                               "age_seconds": round(age_seconds) if age_seconds is not None else None,
                               "fresh": fresh, "issue": issue})
    except httpx.RequestError as exc:
        raise HTTPException(502, "Home Assistant ni dosegljiv iz GrowMaster backend vsebnika.") from exc
    summary = {}
    for unit in {item.get("unit") for item in result if item.get("numeric_value") is not None}:
        group = [item["numeric_value"] for item in result if item.get("unit") == unit and item.get("numeric_value") is not None]
        summary[str(unit or "brez enote")] = {"count": len(group), "mean": round(sum(group) / len(group), 3),
                                             "minimum": min(group), "maximum": max(group)}
    group_rows = []
    for group in groups:
        assigned = sum(1 for row in db.scalars(select(IrrigationBedProfile).where(IrrigationBedProfile.farm_id == FARM_ID))
                       if (profile := BedProfile.model_validate_json(row.parameters)).mode == "soil_sensor" and profile.wh51_group == group.group_number)
        group_rows.append({"group_number": group.group_number, "name": group.name, "entity_id": group.entity_id,
                           "assigned_beds": assigned})
    return {"entities": result, "sensor_groups": group_rows, "numeric_summary_by_unit": summary,
            "configured_wh51_count": sum(1 for group in groups if group.entity_id),
            "maximum_wh51_count": 16, "automatic_execution": False,
            "note": "Prebrane so samo vrednosti entity-jev. GrowMaster jih še ne uporablja za izračun in ne odpira ventilov."}


@router.post("/home-assistant/smart-irrigation")
def send_smart_irrigation(day: date, db: Session = Depends(get_db)):
    """Send only validated Kc multipliers; never call an irrigation controller."""
    base_url, token = home_assistant_config()
    if not base_url:
        raise HTTPException(503, "Najprej nastavi HOME_ASSISTANT_URL in HOME_ASSISTANT_TOKEN na strežniku GrowMaster.")
    preview = smart_irrigation_preview(day, db)
    ready = [row for row in preview["rows"] if row["status"] == "draft"]
    if not ready:
        raise HTTPException(409, "Ni veljavnih Kc posodobitev. Preveri aktivno kulturo, profil kulture in Smart Irrigation cono.")
    sent = []
    blocked = [row for row in preview["rows"] if row["status"] != "draft"]
    try:
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            for row in ready:
                action = row["action"]
                response = client.post(
                    f"{base_url}/api/services/smart_irrigation/set_multiplier",
                    headers=ha_headers(token),
                    json={**action["target"], **action["data"]},
                )
                if response.status_code == 401:
                    raise HTTPException(502, "Home Assistant je zavrnil žeton; posodobitev ni potrjena.")
                if response.status_code not in {200, 201}:
                    raise HTTPException(502, f"Home Assistant je zavrnil posodobitev cone (HTTP {response.status_code}).")
                sent.append({"bed_id": row["bed_id"], "bed": row["bed"], **action["target"],
                             "multiplier": row["multiplier"], "status": "sent"})
    except httpx.RequestError as exc:
        raise HTTPException(502, "Prekinjena je bila povezava s Home Assistantom; preveri stanje con pred ponovitvijo.") from exc
    return {"day": preview["day"], "sent": sent,
            "blocked": [{"bed_id": row["bed_id"], "bed": row["bed"], "reasons": row["reasons"]} for row in blocked],
            "automatic_execution": False,
            "note": "Posodobljeni so samo Kc multiplikatorji Smart Irrigation. Ventili niso bili zagnani."}
