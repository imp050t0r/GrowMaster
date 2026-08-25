from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.master_data_service import (
    master_data_path,
    read_master_data,
    synchronize_master_data,
    write_master_data,
)


router = APIRouter()


@router.get("/api/system/master-data")
def master_data_status() -> dict:
    path = master_data_path()
    return {
        "path": str(path),
        "exists": path.exists(),
        "message": (
            "Master-data datoteka obstaja in jo lahko urejaš brez spremembe aplikacije."
            if path.exists()
            else "Master-data datoteka še ne obstaja. Najprej jo izvozi iz trenutne baze."
        ),
    }


@router.post("/api/system/master-data/export")
def export_master_data(db: Session = Depends(get_db)) -> dict:
    path = write_master_data(db)
    return {
        "message": "Trenutni katalog kultur in sort je izvožen v master-data datoteko.",
        "path": str(path),
    }


@router.post("/api/system/master-data/reload")
def reload_master_data(db: Session = Depends(get_db)) -> dict:
    try:
        payload = read_master_data()
        result = synchronize_master_data(db, payload)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Master-data datoteka ne obstaja. Najprej izvedi izvoz.",
        ) from error
    except (ValueError, KeyError, TypeError) as error:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=f"Master-data datoteka ni veljavna: {error}",
        ) from error
    return {
        "message": "Master-data datoteka je ponovno naložena in baza sinhronizirana.",
        **result,
    }
