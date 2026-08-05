from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import Base, SessionLocal, engine, get_db
from app.models import Bed, Crop, Planting, Task, Variety
from app.schemas import (
    BedCreate,
    CropOut,
    PlantingCreate,
    RotationPreview,
    TaskComplete,
    TaskCreate,
)
from app.seed import seed_database

DEFAULT_FARM_ID = 1


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(title="GrowMaster API", version="0.2.0", lifespan=lifespan)
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


def serialize_planting(planting: Planting) -> dict:
    return {
        "id": planting.id,
        "bed": planting.bed.name if planting.bed else None,
        "crop": planting.crop.name,
        "crop_family": planting.crop.family,
        "variety": planting.variety.name,
        "sowing_date": planting.sowing_date,
        "expected_harvest_date": planting.expected_harvest_date,
        "status": planting.status,
        "rotation_override": planting.rotation_override,
    }


def serialize_task(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "task_type": task.task_type,
        "due_date": task.due_date,
        "status": task.status,
        "priority": task.priority,
        "bed_id": task.bed_id,
        "bed": task.bed.name if task.bed else None,
        "planting_id": task.planting_id,
        "completed_at": task.completed_at,
        "duration_minutes": task.duration_minutes,
        "quantity_used": task.quantity_used,
        "unit": task.unit,
        "notes": task.notes,
    }


@app.get("/api/dashboard")
def dashboard(
    dashboard_date: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
) -> dict:
    target_date = dashboard_date or date.today()
    tasks = db.scalars(
        select(Task)
        .where(Task.farm_id == DEFAULT_FARM_ID, Task.due_date == target_date)
        .options(selectinload(Task.bed))
        .order_by(Task.status, Task.priority.desc(), Task.id)
    ).all()
    active_plantings = db.scalars(
        select(Planting)
        .where(Planting.farm_id == DEFAULT_FARM_ID, Planting.status == "active")
        .options(selectinload(Planting.bed), selectinload(Planting.crop), selectinload(Planting.variety))
        .order_by(Planting.expected_harvest_date)
    ).all()
    return {
        "date": target_date,
        "tasks_total": len(tasks),
        "tasks_completed": sum(task.status == "completed" for task in tasks),
        "active_beds": len(active_plantings),
        "next_harvest": serialize_planting(active_plantings[0]) if active_plantings else None,
        "tasks": [serialize_task(task) for task in tasks],
    }


@app.get("/api/beds")
def list_beds(db: Session = Depends(get_db)) -> list[dict]:
    beds = db.scalars(
        select(Bed).where(Bed.farm_id == DEFAULT_FARM_ID).order_by(Bed.name)
    ).all()
    result = []
    for bed in beds:
        current = active_planting_for_bed(db, bed.id)
        open_task = db.scalar(
            select(Task)
            .where(Task.bed_id == bed.id, Task.status == "planned")
            .limit(1)
        )
        result.append(
            {
                "id": bed.id,
                "name": bed.name,
                "width_m": bed.width_m,
                "length_m": bed.length_m,
                "area_m2": bed.area_m2,
                "status": bed.status,
                "last_crop_family": bed.last_crop_family,
                "has_open_tasks": open_task is not None,
                "current_planting": None if current is None else serialize_planting(current),
            }
        )
    return result


@app.post("/api/beds", status_code=status.HTTP_201_CREATED)
def create_bed(payload: BedCreate, db: Session = Depends(get_db)) -> dict:
    normalized_name = payload.name.strip().upper()
    duplicate = db.scalar(
        select(Bed).where(Bed.farm_id == DEFAULT_FARM_ID, Bed.name == normalized_name)
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Gredica s tem imenom že obstaja.")

    bed = Bed(
        farm_id=DEFAULT_FARM_ID,
        name=normalized_name,
        width_m=payload.width_m,
        length_m=payload.length_m,
        status="empty",
    )
    db.add(bed)
    db.commit()
    db.refresh(bed)
    return {
        "id": bed.id,
        "name": bed.name,
        "width_m": bed.width_m,
        "length_m": bed.length_m,
        "area_m2": bed.area_m2,
        "status": bed.status,
    }


@app.get("/api/beds/{bed_id}")
def bed_detail(bed_id: int, db: Session = Depends(get_db)) -> dict:
    bed = db.get(Bed, bed_id)
    if bed is None or bed.farm_id != DEFAULT_FARM_ID:
        raise HTTPException(status_code=404, detail="Gredica ne obstaja.")

    plantings = db.scalars(
        select(Planting)
        .where(Planting.bed_id == bed.id)
        .options(selectinload(Planting.bed), selectinload(Planting.crop), selectinload(Planting.variety))
        .order_by(Planting.sowing_date.desc(), Planting.id.desc())
    ).all()
    tasks = db.scalars(
        select(Task)
        .where(Task.bed_id == bed.id)
        .options(selectinload(Task.bed))
        .order_by(Task.due_date.desc(), Task.id.desc())
        .limit(20)
    ).all()
    current = next((planting for planting in plantings if planting.status == "active"), None)

    return {
        "id": bed.id,
        "name": bed.name,
        "width_m": bed.width_m,
        "length_m": bed.length_m,
        "area_m2": bed.area_m2,
        "status": bed.status,
        "last_crop_family": bed.last_crop_family,
        "current_planting": serialize_planting(current) if current else None,
        "history": [serialize_planting(planting) for planting in plantings],
        "tasks": [serialize_task(task) for task in tasks],
    }


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
    return [serialize_planting(planting) for planting in db.scalars(statement).all()]


def add_automatic_tasks(db: Session, planting: Planting, bed: Bed) -> None:
    schedule = [
        ("Pregled vznika", "emergence_check", planting.sowing_date + timedelta(days=7), "normal"),
        ("Pregled rasti", "growth_check", planting.sowing_date + timedelta(days=21), "normal"),
        (
            "Kontrola pred žetvijo",
            "harvest_check",
            planting.expected_harvest_date - timedelta(days=1),
            "high",
        ),
    ]
    for title, task_type, due_date, priority in schedule:
        db.add(
            Task(
                farm_id=DEFAULT_FARM_ID,
                bed_id=bed.id,
                planting_id=planting.id,
                title=f"{title}: {planting.crop.name} {planting.variety.name}",
                task_type=task_type,
                due_date=due_date,
                priority=priority,
            )
        )


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
        expected_harvest_date=payload.sowing_date + timedelta(days=variety.days_to_harvest),
        rotation_override=payload.override_rotation,
        status="active",
    )
    bed.status = "growing"
    db.add(planting)
    db.flush()
    planting.crop = crop
    planting.variety = variety
    add_automatic_tasks(db, planting, bed)
    db.commit()
    db.refresh(planting)

    return {
        "id": planting.id,
        "message": f"Setev je dodana na gredico {bed.name}; ustvarjena so tudi tri opravila.",
        "bed": bed.name,
        "crop": crop.name,
        "variety": variety.name,
        "expected_harvest_date": planting.expected_harvest_date,
    }


@app.post("/api/plantings/{planting_id}/finish")
def finish_planting(planting_id: int, db: Session = Depends(get_db)) -> dict:
    planting = db.scalar(
        select(Planting)
        .where(Planting.id == planting_id, Planting.farm_id == DEFAULT_FARM_ID)
        .options(selectinload(Planting.bed), selectinload(Planting.crop))
    )
    if planting is None:
        raise HTTPException(status_code=404, detail="Rastni cikel ne obstaja.")
    if planting.status != "active":
        raise HTTPException(status_code=409, detail="Rastni cikel je že zaključen.")

    planting.status = "completed"
    planting.bed.status = "empty"
    planting.bed.last_crop_family = planting.crop.family
    db.commit()
    return {"message": f"Rastni cikel na gredici {planting.bed.name} je zaključen."}


@app.get("/api/tasks")
def list_tasks(
    task_date: date | None = Query(default=None, alias="date"),
    include_completed: bool = True,
    db: Session = Depends(get_db),
) -> list[dict]:
    target_date = task_date or date.today()
    statement = (
        select(Task)
        .where(Task.farm_id == DEFAULT_FARM_ID, Task.due_date == target_date)
        .options(selectinload(Task.bed))
        .order_by(Task.status, Task.priority.desc(), Task.id)
    )
    if not include_completed:
        statement = statement.where(Task.status != "completed")
    return [serialize_task(task) for task in db.scalars(statement).all()]


@app.post("/api/tasks", status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> dict:
    bed = None
    planting = None
    if payload.bed_id is not None:
        bed = db.get(Bed, payload.bed_id)
        if bed is None or bed.farm_id != DEFAULT_FARM_ID:
            raise HTTPException(status_code=404, detail="Izbrana gredica ne obstaja.")
    if payload.planting_id is not None:
        planting = db.get(Planting, payload.planting_id)
        if planting is None or planting.farm_id != DEFAULT_FARM_ID:
            raise HTTPException(status_code=404, detail="Izbrana setev ne obstaja.")
        if bed is not None and planting.bed_id != bed.id:
            raise HTTPException(status_code=422, detail="Setev ne pripada izbrani gredici.")

    task = Task(
        farm_id=DEFAULT_FARM_ID,
        bed_id=bed.id if bed else None,
        planting_id=planting.id if planting else None,
        title=payload.title.strip(),
        task_type=payload.task_type,
        due_date=payload.due_date,
        priority=payload.priority,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"id": task.id, "message": "Opravilo je dodano.", **serialize_task(task)}


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: int, payload: TaskComplete, db: Session = Depends(get_db)) -> dict:
    task = db.scalar(
        select(Task)
        .where(Task.id == task_id, Task.farm_id == DEFAULT_FARM_ID)
        .options(selectinload(Task.bed))
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Opravilo ne obstaja.")
    if task.status == "completed":
        raise HTTPException(status_code=409, detail="Opravilo je že zaključeno.")

    task.status = "completed"
    task.completed_at = datetime.now()
    task.duration_minutes = payload.duration_minutes
    task.quantity_used = payload.quantity_used
    task.unit = payload.unit.strip() if payload.unit else None
    task.notes = payload.notes.strip() if payload.notes else None
    db.commit()
    db.refresh(task)
    return {"message": "Opravilo je zaključeno.", **serialize_task(task)}
