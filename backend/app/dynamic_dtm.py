"""Advisory maturity estimates; never rewrite catalog or operational dates.

GDD uses Celsius daily means above a crop-specific base. A thermal target
must be supplied explicitly; calendar DTM is not a thermal calibration.
"""
from datetime import date, datetime, timedelta, timezone
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.maturity import maturity_days_for_date, season_for_date

ENGINE_VERSION = "1.24.34"
DTM_COLUMNS = {
    "dynamic_dtm_days": "INTEGER",
    "dynamic_dtm_confidence": "VARCHAR(20)",
    "predicted_harvest_start": "DATE",
    "predicted_harvest_end": "DATE",
    "dynamic_dtm_explanation": "TEXT",
    "dynamic_dtm_initial_snapshot": "TEXT",
}


class TemperatureDay(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    day: date
    mean_c: float = Field(ge=-60, le=65)
    kind: Literal["observed", "forecast", "climatology"]


class ClimateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    source: str | None = Field(default=None, min_length=1, max_length=240)
    calibration_source: str | None = Field(default=None, min_length=1, max_length=240)
    base_temperature_c: float | None = Field(default=None, ge=-10, le=35)
    target_gdd: float | None = Field(default=None, gt=0, le=20000)
    temperatures: list[TemperatureDay] = Field(default_factory=list, max_length=730)

    @model_validator(mode="after")
    def validate_days(self):
        days = [item.day for item in self.temperatures]
        if len(days) != len(set(days)):
            raise ValueError("Temperaturni podatki vsebujejo podvojene datume.")
        if any(item.kind == "observed" and item.day > date.today() for item in self.temperatures):
            raise ValueError("Prihodnja temperatura ne more biti označena kot izmerjena.")
        return self


def predict(variety, reference_date: date, climate: ClimateInput | None = None,
            reference_kind: str = "sowing", planned_harvest_date: date | None = None) -> dict:
    climate = climate or ClimateInput()
    base = int(variety.days_to_harvest)
    seasonal = maturity_days_for_date(variety, reference_date)
    days = seasonal
    method = "seasonal_fallback"
    confidence = "low"
    reasons = ["Sezonska ocena iz obstoječih podatkov sorte; ne gre za lokalno umerjen model."]
    accumulated = 0.0
    used = []
    calibrated = (climate.base_temperature_c is not None and climate.target_gdd is not None
                  and bool((climate.calibration_source or "").strip())
                  and bool((climate.source or "").strip()))
    if calibrated and climate.temperatures:
        by_day = {item.day: item for item in climate.temperatures}
        # Only a continuous series from the reference date can establish maturity.
        # Missing or short forecasts do not justify extrapolating recent heat.
        for offset in range(730):
            item = by_day.get(reference_date + timedelta(days=offset))
            if item is None:
                break
            accumulated += max(0.0, item.mean_c - climate.base_temperature_c)
            used.append(item)
            if accumulated >= climate.target_gdd:
                days = offset + 1
                method = "gdd"
                confidence = "medium" if all(x.kind == "observed" for x in used) else "low"
                reasons = ["Dosežen izrecno podani GDD cilj z neprekinjenim nizom dnevnih temperatur.",
                           "GDD nadomesti sezonsko oceno; popravka se ne seštevata."]
                break
        if method != "gdd":
            reasons.append("Temperaturni niz je nepopoln ali ne doseže GDD cilja; uporabljena je sezonska ocena.")
    else:
        reasons.append("Manjkajo temperature, vir podatkov ali umerjeni GDD parametri; temperaturni popravek ni uporabljen.")
    reasons.append("Fotoperiodni popravek ni uporabljen: ni umerjenega odziva sorte na dolžino dneva.")
    reasons.append("Zanesljivost označuje kakovost vhodov, ne statistične verjetnosti; interval je načrtovalna ocena.")
    center = reference_date + timedelta(days=days)
    margin = max(2, math.ceil(days * (0.15 if confidence == "medium" else 0.25)))
    return {
        "engine_version": ENGINE_VERSION,
        "catalog_dtm_days": base,
        "seasonal_dtm_days": seasonal,
        "season": season_for_date(reference_date),
        "dynamic_dtm_days": days,
        "adjustment_days": days - base,
        "reference_date": reference_date.isoformat(),
        "reference_kind": reference_kind,
        "planned_harvest_date": planned_harvest_date.isoformat() if planned_harvest_date else None,
        "predicted_harvest_date": center.isoformat(),
        "predicted_harvest_start": (reference_date + timedelta(days=max(1, days - margin))).isoformat(),
        "predicted_harvest_end": (center + timedelta(days=margin)).isoformat(),
        "confidence": confidence,
        "method": method,
        "fallback": method == "seasonal_fallback",
        "gdd_accumulated": round(accumulated, 2) if calibrated else None,
        "temperature_days_used": len(used),
        "inputs": climate.model_dump(mode="json"),
        "reasons": reasons,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }


def store_prediction(record, variety, climate=None, reference_date=None, reference_kind=None):
    reference_date = reference_date or getattr(record, "transplant_date", None) or record.sowing_date
    reference_kind = reference_kind or ("transplant" if getattr(record, "transplant_date", None) else "sowing")
    result = predict(variety, reference_date, climate, reference_kind, record.expected_harvest_date)
    record.dynamic_dtm_days = result["dynamic_dtm_days"]
    record.dynamic_dtm_confidence = result["confidence"]
    record.predicted_harvest_start = date.fromisoformat(result["predicted_harvest_start"])
    record.predicted_harvest_end = date.fromisoformat(result["predicted_harvest_end"])
    record.dynamic_dtm_explanation = json.dumps(result, ensure_ascii=False)
    if not record.dynamic_dtm_initial_snapshot:
        record.dynamic_dtm_initial_snapshot = record.dynamic_dtm_explanation
    return result


def serialized_prediction(record):
    return json.loads(record.dynamic_dtm_explanation) if record.dynamic_dtm_explanation else None
