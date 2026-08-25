from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.master_data_service import read_master_data, synchronize_master_data
from app.plant_db_service import ensure_external_files, load_rotation_rules, status


router = APIRouter()


def _reload_rotation_globals() -> dict:
    from app import planting_advisor

    payload = load_rotation_rules()
    planting_advisor._RULES = payload
    planting_advisor.MIXTURE_ROTATION_FAMILIES = {
        name: set(families)
        for name, families in payload["mixture_rotation_families"].items()
    }
    planting_advisor.WARM_SEASON_CROPS = set(payload["warm_season_crops"])
    planting_advisor.WINTER_FRIENDLY_CROPS = set(payload["winter_friendly_crops"])
    planting_advisor.ROTATION_RULES.clear()
    planting_advisor.ROTATION_RULES.update(payload["rotation"])
    return {
        "mixture_count": len(planting_advisor.MIXTURE_ROTATION_FAMILIES),
        "warm_season_count": len(planting_advisor.WARM_SEASON_CROPS),
        "winter_friendly_count": len(planting_advisor.WINTER_FRIENDLY_CROPS),
    }


@router.get("/api/system/plant-db")
def plant_db_status() -> dict:
    return status()


@router.post("/api/system/plant-db/initialize")
def initialize_plant_db() -> dict:
    return {
        "message": "Zunanja Plant DB struktura je pripravljena. Vgrajeni podatki ostanejo samo fallback.",
        **ensure_external_files(),
    }


@router.post("/api/system/plant-db/reload")
def reload_plant_db(db: Session = Depends(get_db)) -> dict:
    try:
        ensure_external_files()
        crop_result = None
        try:
            crop_result = synchronize_master_data(db, read_master_data())
        except FileNotFoundError:
            crop_result = {"message": "growmaster-crops.json še ne obstaja; katalog kultur v PostgreSQL ni bil spremenjen."}
        rotation_result = _reload_rotation_globals()
        current = status()
    except (ValueError, KeyError, TypeError) as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"Plant DB ni veljavna: {error}") from error
    return {
        "message": "Plant DB je ponovno naložena brez novega GrowMaster releasa.",
        "crops": crop_result,
        "rotation": rotation_result,
        **current,
    }
