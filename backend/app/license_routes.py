from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.license_service import activate, status


router = APIRouter()


class LicenseActivation(BaseModel):
    token: str = Field(min_length=40, max_length=10000)


@router.get("/api/license/status")
def license_status() -> dict:
    return status()


@router.post("/api/license/activate")
def activate_license(body: LicenseActivation) -> dict:
    try:
        current = activate(body.token)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"message": "GrowMaster je uspešno aktiviran.", **current}
