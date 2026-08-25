from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.master_data_service import master_data_path, read_master_data, write_master_data
from app.models import Crop, Variety
from app.seeding_profiles import export_seeding_data, load_seeding_data, seeding_data_path, seeding_profile

router = APIRouter()


class LearningApply(BaseModel):
    crop: str = Field(min_length=1, max_length=120)
    variety: str = Field(min_length=1, max_length=120)
    new_seed_rate_g_m2: float | None = Field(default=None, gt=0, le=100)
    new_days_to_harvest: int | None = Field(default=None, ge=1, le=730)
    reason: str = Field(default="Potrjen GrowMaster learning predlog", max_length=500)


def _patch_master_file(crop_name: str, variety_name: str, seed_rate: float | None, dtm: int | None) -> None:
    payload = read_master_data()
    found = False
    for crop in payload.get("crops", []):
        if crop.get("name", "").casefold() != crop_name.casefold():
            continue
        for variety in crop.get("varieties", []):
            if variety.get("name", "").casefold() != variety_name.casefold():
                continue
            if seed_rate is not None:
                variety["seed_rate_g_m2"] = seed_rate
            if dtm is not None:
                variety["days_to_harvest"] = dtm
            found = True
            break
    if not found:
        raise ValueError("Kultura/sorta ni najdena v master-data datoteki.")
    master_data_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _patch_seeding_file(crop_name: str, variety_name: str, seed_rate: float) -> None:
    export_seeding_data()
    payload = load_seeding_data()
    profiles = payload.setdefault("profiles", {})
    crop_profile = profiles.setdefault(crop_name, {})
    varieties = crop_profile.setdefault("varieties", {})
    variety_profile = varieties.setdefault(variety_name, {})
    variety_profile["seed_rate_g_m2"] = seed_rate
    seeding_data_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@router.post("/api/master-data/backfill-seeding")
def backfill_seeding_master_data(dry_run: bool = True, db: Session = Depends(get_db)) -> dict:
    crops = list(db.scalars(select(Crop).options(selectinload(Crop.varieties))).all())
    changes = []
    for crop in crops:
        for variety in crop.varieties:
            if variety.seed_rate_g_m2 is not None:
                continue
            profile = seeding_profile(crop.name, variety.name, crop.family, crop.category)
            rate = profile.get("seed_rate_g_m2")
            if rate is None:
                continue
            changes.append({"crop": crop.name, "variety": variety.name, "field": "seed_rate_g_m2", "old": None, "new": float(rate), "basis": profile.get("profile_basis")})
            if not dry_run:
                variety.seed_rate_g_m2 = float(rate)
    if not dry_run and changes:
        db.commit()
        write_master_data(db)
    return {"dry_run": dry_run, "change_count": len(changes), "changes": changes, "message": "Najprej uporabi dry_run=true; apply z dry_run=false zapiše samo že eksplicitno konfigurirane setvene norme."}


@router.post("/api/agronomy/learning/apply")
def apply_learning(body: LearningApply, db: Session = Depends(get_db)) -> dict:
    crop = db.scalar(select(Crop).where(Crop.name.ilike(body.crop)).options(selectinload(Crop.varieties)))
    if crop is None:
        raise HTTPException(status_code=404, detail="Kultura ni najdena.")
    variety = next((item for item in crop.varieties if item.name.casefold() == body.variety.casefold()), None)
    if variety is None:
        raise HTTPException(status_code=404, detail="Sorta ni najdena.")
    before = {"seed_rate_g_m2": variety.seed_rate_g_m2, "days_to_harvest": variety.days_to_harvest}
    if body.new_seed_rate_g_m2 is None and body.new_days_to_harvest is None:
        raise HTTPException(status_code=400, detail="Podaj vsaj eno novo vrednost.")
    if body.new_seed_rate_g_m2 is not None:
        variety.seed_rate_g_m2 = body.new_seed_rate_g_m2
    if body.new_days_to_harvest is not None:
        variety.days_to_harvest = body.new_days_to_harvest
    db.commit()
    write_master_data(db)
    try:
        _patch_master_file(crop.name, variety.name, body.new_seed_rate_g_m2, body.new_days_to_harvest)
        if body.new_seed_rate_g_m2 is not None:
            _patch_seeding_file(crop.name, variety.name, body.new_seed_rate_g_m2)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Baza je posodobljena, zunanja master datoteka pa ne: {exc}") from exc
    audit = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "crop": crop.name,
        "variety": variety.name,
        "before": before,
        "after": {"seed_rate_g_m2": variety.seed_rate_g_m2, "days_to_harvest": variety.days_to_harvest},
        "reason": body.reason,
    }
    return {"message": "Learning predlog je potrjeno zapisan v PostgreSQL in master-data datoteke.", "audit": audit}
