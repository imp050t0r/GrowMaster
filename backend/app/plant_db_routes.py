from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.master_data_service import read_master_data, synchronize_master_data, write_master_data
from app.models import Crop
from app.plant_db_review import classify_entries, mark_review, review_summary
from app.plant_db_service import (
    ensure_external_files,
    fetch_remote_files,
    load_rotation_rules,
    record_partial_update_version,
    remote_update_status,
    status,
)


router = APIRouter()


class PlantDbSelection(BaseModel):
    entries: list[str] = Field(default_factory=list, max_length=5000)
    shown_entries: list[str] = Field(default_factory=list, max_length=5000)


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


def _remote_crop_payload(staged: dict[str, bytes]) -> dict:
    payload = json.loads(staged["crops"].decode("utf-8"))
    if not isinstance(payload.get("crops"), list):
        raise ValueError("Oddaljena Plant DB nima veljavnega seznama kultur.")
    return payload


def _preview_new_entries(db: Session, remote_payload: dict) -> list[dict]:
    existing_crops = {
        crop.name.casefold(): crop
        for crop in db.scalars(select(Crop).options(selectinload(Crop.varieties))).all()
    }
    result: list[dict] = []
    for crop_data in remote_payload["crops"]:
        crop_name = str(crop_data.get("name") or "").strip()
        if not crop_name:
            continue
        crop = existing_crops.get(crop_name.casefold())
        if crop is None:
            varieties = [str(item.get("name") or "").strip() for item in crop_data.get("varieties", [])]
            varieties = [item for item in varieties if item]
            result.append({
                "key": f"crop::{crop_name}",
                "type": "crop",
                "crop": crop_name,
                "variety": None,
                "label": crop_name,
                "detail": f"Nova kultura · {len(varieties)} sort",
                "variety_count": len(varieties),
            })
            continue
        existing_varieties = {item.name.casefold() for item in crop.varieties}
        for variety_data in crop_data.get("varieties", []):
            variety_name = str(variety_data.get("name") or "").strip()
            if variety_name and variety_name.casefold() not in existing_varieties:
                result.append({
                    "key": f"variety::{crop_name}::{variety_name}",
                    "type": "variety",
                    "crop": crop_name,
                    "variety": variety_name,
                    "label": f"{crop_name} · {variety_name}",
                    "detail": "Nova sorta",
                    "variety_count": 1,
                })
    return result


def _selected_payload(remote_payload: dict, keys: set[str]) -> dict:
    selected = {"schema_version": remote_payload.get("schema_version", 1), "crops": []}
    for crop_data in remote_payload["crops"]:
        crop_name = str(crop_data.get("name") or "").strip()
        crop_key = f"crop::{crop_name}"
        if crop_key in keys:
            selected["crops"].append(crop_data)
            continue
        varieties = [
            variety
            for variety in crop_data.get("varieties", [])
            if f"variety::{crop_name}::{str(variety.get('name') or '').strip()}" in keys
        ]
        if varieties:
            selected["crops"].append({
                "name": crop_data["name"],
                "family": crop_data["family"],
                "category": crop_data["category"],
                "varieties": varieties,
            })
    return selected


@router.get("/api/system/plant-db")
def plant_db_status() -> dict:
    return {**status(), "review": review_summary()}


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


@router.get("/api/system/plant-db/update-status")
def plant_db_update_status() -> dict:
    try:
        return {**remote_update_status(), "review": review_summary()}
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(status_code=502, detail=f"Preverjanje Plant DB ni uspelo: {error}") from error


@router.get("/api/system/plant-db/update-preview")
def preview_plant_db_update(
    include_skipped: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    try:
        manifest, staged = fetch_remote_files()
        remote_payload = _remote_crop_payload(staged)
        all_missing = _preview_new_entries(db, remote_payload)
        fresh, skipped = classify_entries(all_missing, include_skipped=include_skipped)
        entries = fresh + skipped
        return {
            "available_version": manifest["plant_db_version"],
            "new_entry_count": len(fresh),
            "skipped_entry_count": len(skipped),
            "entries": entries,
            "fresh_entries": fresh,
            "skipped_entries": skipped,
            "review": review_summary(),
            "message": "Prikazane so samo res nove postavke od zadnjega pregleda. Prej preskočene so skrite, razen če jih uporabnik posebej odpre.",
            "existing_values_preserved": True,
        }
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(status_code=502, detail=f"Predogled Plant DB ni uspel: {error}") from error


@router.post("/api/system/plant-db/update")
def update_plant_db(body: PlantDbSelection, db: Session = Depends(get_db)) -> dict:
    try:
        manifest, staged = fetch_remote_files()
        remote_payload = _remote_crop_payload(staged)
        all_missing = _preview_new_entries(db, remote_payload)
        available = {item["key"] for item in all_missing}
        requested = set(body.entries)
        shown = set(body.shown_entries) if body.shown_entries else requested
        unknown = (requested | shown) - available
        if unknown:
            raise ValueError("Izbira vsebuje postavke, ki niso več na voljo v predogledu.")

        mark_review(manifest["plant_db_version"], shown, requested)

        if not requested:
            return {
                "message": "Prikazane novosti so označene kot pregledane. Nobena postavka ni bila dodana.",
                "skipped": True,
                "available_version": manifest["plant_db_version"],
                "review": review_summary(),
                **status(),
            }

        payload = _selected_payload(remote_payload, requested)
        result = synchronize_master_data(db, payload)
        write_master_data(db)
        record_partial_update_version(manifest["plant_db_version"], {
            "mode": "delta-selected",
            "approved_entries": sorted(requested),
            "reviewed_entries": sorted(shown),
        })
        remaining_all = _preview_new_entries(db, remote_payload)
        remaining_fresh, _ = classify_entries(remaining_all, include_skipped=False)
        return {
            "message": "Izbrane nove postavke so dodane. Ostale prikazane novosti so shranjene kot pregledane/preskočene.",
            "added": result,
            "approved_entry_count": len(requested),
            "remaining_new_entry_count": len(remaining_fresh),
            "review": review_summary(),
            "existing_values_preserved": True,
            **status(),
        }
    except (OSError, ValueError, KeyError, TypeError) as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"Posodobitev Plant DB ni uspela: {error}") from error
