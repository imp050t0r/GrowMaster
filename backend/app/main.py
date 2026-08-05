from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import Base, SessionLocal, engine, get_db
from app.models import Bed, Crop, Planting, Variety
from app.schemas import CropOut, PlantingCreate, RotationPreview
from app.seed import seed_database

DEFAULT_FARM_ID = 1


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(title="GrowMaster API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"app": "GrowMaster", "status": "running"}


@app.get("/api/crops", response_model=list[CropOut])
def list_crops(db: Session = Depends(get_db)) -> list[Crop]:
    statement = select(Crop).options(selectinload(Crop.varieties)).order_by(Crop.name)
    return list(db.scalars(statement).all())


def active_planting_for_bed(db: Session, bed_id: int) -> Planting | None:
    statement = (
        select(Planting)
        .where(Planting.bed_id == bed_id, Planting.status == "active")
        .options(selectinload(Planting.crop), selectinload(Planting.variety))
        .order_by(Planting.created_at.desc())
        .limit(1)
    )
    return db.scalar(statement)


@app.get("/api/beds")
def list_beds(db: Session = Depends(get_db)) -> list[dict]:
    beds = db.scalars(
        select(Bed).where(Bed.farm_id == DEFAULT_FARM_ID).order_by(Bed.name)
    ).all()
    result = []
    for bed in beds:
        current = active_planting_for_bed(db, bed.id)
        result.append(
            {
                "id": bed.id,
                "name": bed.name,
                "width_m": bed.width_m,
                "length_m": bed.length_m,
                "area_m2": bed.area_m2,
                "status": bed.status,
                "last_crop_family": bed.last_crop_family,
                "current_planting": None
                if current is None
                else {
                    "id": current.id,
                    "crop": current.crop.name,
                    "variety": current.variety.name,
                    "sowing_date": current.sowing_date,
                    "expected_harvest_date": current.expected_harvest_date,
                },
            }
        )
    return result


def resolve_selection(payload: PlantingCreate, db: Session) -> tuple[Crop, Variety, Bed]:
    crop = db.get(Crop, payload.crop_id)
    variety = db.get(Variety, payload.variety_id)
    bed = db.get(Bed, payload.bed_id)

    if crop is None or variety is None or bed is None:
        raise HTTPException(status_code=404, detail="Kultura, sorta ali gredica ne obstaja.")
    if variety.crop_id != crop.id:
        raise HTTPException(status_code=422, detail="Izbrana sorta ne pripada izbrani kulturi.")
    if bed.farm_id != DEFAULT_FARM_ID:
        raise HTTPException(status_code=403, detail="Gredica ne pripada aktivni kmetiji.")
    return crop, variety, bed


def rotation_preview(payload: PlantingCreate, db: Session) -> RotationPreview:
    crop, _, bed = resolve_selection(payload, db)
    active = active_planting_for_bed(db, bed.id)
    if active is not None:
        return RotationPreview(
            allowed=False,
            code="BED_OCCUPIED",
            message=f"Gredica {bed.name} je že zasedena: {active.crop.name} {active.variety.name}.",
        )

    if bed.last_crop_family == crop.family:
        return RotationPreview(
            allowed=True,
            requires_override=True,
            code="ROTATION_WARNING",
            message=(
                f"Na gredici {bed.name} je bila nazadnje družina {bed.last_crop_family}. "
                f"Tudi {crop.name} spada v isto družino."
            ),
            warnings=["Priporočena je druga gredica ali daljši presledek v kolobarju."],
        )

    return RotationPreview(allowed=True, message="Gredica je prosta in kolobar je ustrezen.")


@app.post("/api/plantings/preview", response_model=RotationPreview)
def preview_planting(payload: PlantingCreate, db: Session = Depends(get_db)) -> RotationPreview:
    return rotation_preview(payload, db)


@app.get("/api/plantings")
def list_plantings(db: Session = Depends(get_db)) -> list[dict]:
    statement = (
        select(Planting)
        .where(Planting.farm_id == DEFAULT_FARM_ID, Planting.status == "active")
        .options(
            selectinload(Planting.bed),
            selectinload(Planting.crop),
            selectinload(Planting.variety),
        )
        .order_by(Planting.sowing_date.desc())
    )
    return [
        {
            "id": planting.id,
            "bed": planting.bed.name,
            "crop": planting.crop.name,
            "variety": planting.variety.name,
            "sowing_date": planting.sowing_date,
            "expected_harvest_date": planting.expected_harvest_date,
            "status": planting.status,
            "rotation_override": planting.rotation_override,
        }
        for planting in db.scalars(statement).all()
    ]


@app.post("/api/plantings", status_code=status.HTTP_201_CREATED)
def create_planting(payload: PlantingCreate, db: Session = Depends(get_db)) -> dict:
    crop, variety, bed = resolve_selection(payload, db)
    preview = rotation_preview(payload, db)

    if not preview.allowed:
        raise HTTPException(status_code=409, detail=preview.model_dump())
    if preview.requires_override and not payload.override_rotation:
        raise HTTPException(status_code=409, detail=preview.model_dump())

    planting = Planting(
        farm_id=DEFAULT_FARM_ID,
        bed_id=bed.id,
        crop_id=crop.id,
        variety_id=variety.id,
        sowing_date=payload.sowing_date,
        expected_harvest_date=payload.sowing_date
        + timedelta(days=variety.days_to_harvest),
        rotation_override=payload.override_rotation,
        status="active",
    )
    bed.status = "growing"
    db.add(planting)
    db.commit()
    db.refresh(planting)

    return {
        "id": planting.id,
        "message": f"Setev je dodana na gredico {bed.name}.",
        "bed": bed.name,
        "crop": crop.name,
        "variety": variety.name,
        "expected_harvest_date": planting.expected_harvest_date,
    }
