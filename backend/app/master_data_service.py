from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.maturity import estimated_seasonal_days
from app.models import Crop, Variety


MASTER_DATA_FILENAME = "growmaster-crops.json"
MASTER_DATA_SCHEMA_VERSION = 1


def master_data_path() -> Path:
    configured = os.getenv("GROWMASTER_MASTER_DATA_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    root = Path(os.getenv("GROWMASTER_DATA_ROOT", "/data"))
    return root / MASTER_DATA_FILENAME


def serialize_master_data(db: Session) -> dict:
    crops = list(
        db.scalars(
            select(Crop).options(selectinload(Crop.varieties)).order_by(Crop.name)
        ).all()
    )
    return {
        "schema_version": MASTER_DATA_SCHEMA_VERSION,
        "crops": [
            {
                "name": crop.name,
                "family": crop.family,
                "category": crop.category,
                "varieties": [
                    {
                        "name": variety.name,
                        "days_to_harvest": variety.days_to_harvest,
                        "days_spring": variety.days_spring,
                        "days_summer": variety.days_summer,
                        "days_autumn": variety.days_autumn,
                        "days_winter": variety.days_winter,
                        "composition": variety.composition,
                        "source_name": variety.source_name,
                        "source_url": variety.source_url,
                        "seed_forms": variety.seed_forms,
                        "traits": variety.traits,
                        "slovenia_note": variety.slovenia_note,
                        "days_baby": variety.days_baby,
                        "seed_rate_g_m2": variety.seed_rate_g_m2,
                        "seed_spacing_cm": variety.seed_spacing_cm,
                        "row_spacing_cm": variety.row_spacing_cm,
                        "planting_method": variety.planting_method,
                        "outdoor_months": variety.outdoor_months,
                        "protected_months": variety.protected_months,
                        "heat_tolerance": variety.heat_tolerance,
                        "cold_tolerance": variety.cold_tolerance,
                        "planting_calendar_note": variety.planting_calendar_note,
                        "succession_interval_days": variety.succession_interval_days,
                        "calendar_source_url": variety.calendar_source_url,
                        "cultivation_methods": variety.cultivation_methods,
                        "harvest_methods": variety.harvest_methods,
                        "nursery_days": variety.nursery_days,
                        "direct_sow_extra_days": variety.direct_sow_extra_days,
                        "days_outer_leaf": variety.days_outer_leaf,
                        "regrowth_interval_min_days": variety.regrowth_interval_min_days,
                        "regrowth_interval_max_days": variety.regrowth_interval_max_days,
                        "max_regrowth_cuts": variety.max_regrowth_cuts,
                        "days_green_harvest": variety.days_green_harvest,
                        "harvest_interval_days": variety.harvest_interval_days,
                        "harvest_duration_days": variety.harvest_duration_days,
                        "harvest_profile_note": variety.harvest_profile_note,
                        "harvest_source_url": variety.harvest_source_url,
                    }
                    for variety in sorted(crop.varieties, key=lambda item: item.name)
                ],
            }
            for crop in crops
        ],
    }


def write_master_data(db: Session) -> Path:
    path = master_data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = serialize_master_data(db)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def read_master_data() -> dict:
    path = master_data_path()
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != MASTER_DATA_SCHEMA_VERSION:
        raise ValueError("Nepodprta različica GrowMaster master-data datoteke.")
    if not isinstance(payload.get("crops"), list):
        raise ValueError("Master-data datoteka nima veljavnega seznama kultur.")
    return payload


def synchronize_master_data(db: Session, payload: dict | None = None) -> dict:
    payload = payload or read_master_data()
    existing_crops = {
        crop.name.casefold(): crop
        for crop in db.scalars(
            select(Crop).options(selectinload(Crop.varieties))
        ).all()
    }
    created_crops = 0
    updated_crops = 0
    created_varieties = 0
    updated_varieties = 0

    for crop_data in payload["crops"]:
        name = str(crop_data["name"]).strip()
        family = str(crop_data["family"]).strip()
        category = str(crop_data["category"]).strip()
        if not name or not family or not category:
            raise ValueError("Kultura mora imeti ime, družino in kategorijo.")
        crop = existing_crops.get(name.casefold())
        if crop is None:
            crop = Crop(name=name, family=family, category=category)
            db.add(crop)
            db.flush()
            existing_crops[name.casefold()] = crop
            created_crops += 1
        else:
            changed = crop.family != family or crop.category != category
            crop.family = family
            crop.category = category
            if changed:
                updated_crops += 1

        varieties = {item.name.casefold(): item for item in crop.varieties}
        for variety_data in crop_data.get("varieties", []):
            variety_name = str(variety_data["name"]).strip()
            if not variety_name:
                raise ValueError(f"Kultura {name} vsebuje sorto brez imena.")
            days = int(variety_data["days_to_harvest"])
            estimates = estimated_seasonal_days(days)
            values = {
                "days_to_harvest": days,
                "days_spring": int(variety_data.get("days_spring") or estimates["spring"]),
                "days_summer": int(variety_data.get("days_summer") or estimates["summer"]),
                "days_autumn": int(variety_data.get("days_autumn") or estimates["autumn"]),
                "days_winter": int(variety_data.get("days_winter") or estimates["winter"]),
                "composition": variety_data.get("composition"),
                "source_name": variety_data.get("source_name"),
                "source_url": variety_data.get("source_url"),
                "seed_forms": variety_data.get("seed_forms"),
                "traits": variety_data.get("traits"),
                "slovenia_note": variety_data.get("slovenia_note"),
                "days_baby": variety_data.get("days_baby"),
                "seed_rate_g_m2": variety_data.get("seed_rate_g_m2"),
                "seed_spacing_cm": variety_data.get("seed_spacing_cm"),
                "row_spacing_cm": variety_data.get("row_spacing_cm"),
                "planting_method": variety_data.get("planting_method"),
                "outdoor_months": variety_data.get("outdoor_months"),
                "protected_months": variety_data.get("protected_months"),
                "heat_tolerance": variety_data.get("heat_tolerance"),
                "cold_tolerance": variety_data.get("cold_tolerance"),
                "planting_calendar_note": variety_data.get("planting_calendar_note"),
                "succession_interval_days": variety_data.get("succession_interval_days"),
                "calendar_source_url": variety_data.get("calendar_source_url"),
                "cultivation_methods": variety_data.get("cultivation_methods"),
                "harvest_methods": variety_data.get("harvest_methods"),
                "nursery_days": variety_data.get("nursery_days"),
                "direct_sow_extra_days": variety_data.get("direct_sow_extra_days"),
                "days_outer_leaf": variety_data.get("days_outer_leaf"),
                "regrowth_interval_min_days": variety_data.get("regrowth_interval_min_days"),
                "regrowth_interval_max_days": variety_data.get("regrowth_interval_max_days"),
                "max_regrowth_cuts": variety_data.get("max_regrowth_cuts"),
                "days_green_harvest": variety_data.get("days_green_harvest"),
                "harvest_interval_days": variety_data.get("harvest_interval_days"),
                "harvest_duration_days": variety_data.get("harvest_duration_days"),
                "harvest_profile_note": variety_data.get("harvest_profile_note"),
                "harvest_source_url": variety_data.get("harvest_source_url"),
            }
            variety = varieties.get(variety_name.casefold())
            if variety is None:
                variety = Variety(name=variety_name, **values)
                crop.varieties.append(variety)
                varieties[variety_name.casefold()] = variety
                created_varieties += 1
            else:
                changed = any(getattr(variety, key) != value for key, value in values.items())
                for key, value in values.items():
                    setattr(variety, key, value)
                if changed:
                    updated_varieties += 1

    db.commit()
    return {
        "created_crops": created_crops,
        "updated_crops": updated_crops,
        "created_varieties": created_varieties,
        "updated_varieties": updated_varieties,
        "path": str(master_data_path()),
    }
