from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.backup_service import backup_file, backup_owner_id, create_backup, list_backups, restore_backup

router = APIRouter()


class BackupRequest(BaseModel):
    label: str | None = Field(default=None, max_length=40)


class RestoreRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    confirm: str = Field(min_length=1, max_length=32)


@router.get("/api/system/backups")
def backups() -> dict:
    return {"owner_id": backup_owner_id(), "backups": list_backups()}


@router.post("/api/system/backups")
def create(body: BackupRequest) -> dict:
    try:
        return {
            "backup": create_backup(body.label),
            "owner_id": backup_owner_id(),
            "message": "Varnostna kopija je ustvarjena v tvoji ločeni GrowMaster backup mapi.",
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Backup ni uspel: {error}") from error


@router.get("/api/system/backups/{name}/download")
def download(name: str):
    try:
        source = backup_file(name)
        return FileResponse(
            source,
            media_type="application/octet-stream",
            filename=source.name,
            headers={"Cache-Control": "no-store"},
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/api/system/backups/restore")
def restore(body: RestoreRequest) -> dict:
    if body.confirm != "OBNOVI":
        raise HTTPException(status_code=422, detail="Za obnovitev vpiši OBNOVI.")
    try:
        return {**restore_backup(body.name), "message": "Backup je obnovljen. Osveži ali ponovno zaženi GrowMaster."}
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Obnova ni uspela: {error}") from error
