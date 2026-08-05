import csv
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import io
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import Base, SessionLocal, engine, get_db
from app.models import (
    Bed,
    Cost,
    Crop,
    CropPlan,
    Customer,
    CustomerProfile,
    Harvest,
    Order,
    OrderItem,
    Planting,
    RetailSale,
    RetailSaleItem,
    Sale,
    SalesSettings,
    Task,
    Variety,
)
from app.schemas import (
    BedCreate,
    CostCreate,
    CropPlanActivate,
    CropPlanCreate,
    CropPlanStatusUpdate,
    CropOut,
    CustomerCreate,
    HarvestCreate,
    OrderCreate,
    OrderStatusUpdate,
    RetailSaleCreate,
    PlantingCreate,
    RotationPreview,
    SaleCreate,
    SalesSettingsUpdate,
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


app = FastAPI(title="GrowMaster API", version="0.7.0", lifespan=lifespan)
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


def serialize_harvest(harvest: Harvest) -> dict:
    sold_kg = round(sum(sale.quantity_kg for sale in harvest.sales), 2)
    revenue = round(sum(sale.revenue_eur for sale in harvest.sales), 2)
    return {
        "id": harvest.id,
        "planting_id": harvest.planting_id,
        "bed_id": harvest.bed_id,
        "bed": harvest.bed.name,
        "crop": harvest.planting.crop.name,
        "variety": harvest.planting.variety.name,
        "harvest_date": harvest.harvest_date,
        "quantity_kg": harvest.quantity_kg,
        "quality": harvest.quality,
        "notes": harvest.notes,
        "sold_kg": sold_kg,
        "available_kg": round(harvest.quantity_kg - sold_kg, 2),
        "revenue_eur": revenue,
    }


def serialize_cost(cost: Cost) -> dict:
    return {
        "id": cost.id,
        "bed_id": cost.bed_id,
        "bed": cost.bed.name,
        "planting_id": cost.planting_id,
        "cost_date": cost.cost_date,
        "category": cost.category,
        "amount_eur": cost.amount_eur,
        "description": cost.description,
    }


def serialize_sale(sale: Sale) -> dict:
    return {
        "id": sale.id,
        "harvest_id": sale.harvest_id,
        "bed_id": sale.harvest.bed_id,
        "bed": sale.harvest.bed.name,
        "sale_date": sale.sale_date,
        "quantity_kg": sale.quantity_kg,
        "price_per_kg_eur": sale.price_per_kg_eur,
        "revenue_eur": sale.revenue_eur,
        "customer": sale.customer,
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


@app.get("/api/harvests")
def list_harvests(db: Session = Depends(get_db)) -> list[dict]:
    harvests = db.scalars(
        select(Harvest)
        .where(Harvest.farm_id == DEFAULT_FARM_ID)
        .options(
            selectinload(Harvest.bed),
            selectinload(Harvest.sales),
            selectinload(Harvest.planting).selectinload(Planting.crop),
            selectinload(Harvest.planting).selectinload(Planting.variety),
        )
        .order_by(Harvest.harvest_date.desc(), Harvest.id.desc())
    ).all()
    return [serialize_harvest(harvest) for harvest in harvests]


@app.post("/api/harvests", status_code=status.HTTP_201_CREATED)
def create_harvest(payload: HarvestCreate, db: Session = Depends(get_db)) -> dict:
    planting = db.scalar(
        select(Planting)
        .where(Planting.id == payload.planting_id, Planting.farm_id == DEFAULT_FARM_ID)
        .options(selectinload(Planting.bed), selectinload(Planting.crop), selectinload(Planting.variety))
    )
    if planting is None:
        raise HTTPException(status_code=404, detail="Setev ne obstaja.")
    harvest = Harvest(
        farm_id=DEFAULT_FARM_ID,
        bed_id=planting.bed_id,
        planting_id=planting.id,
        harvest_date=payload.harvest_date,
        quantity_kg=payload.quantity_kg,
        quality=payload.quality,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(harvest)
    db.commit()
    db.refresh(harvest)
    harvest.sales = []
    return {"message": "Žetev je zabeležena.", **serialize_harvest(harvest)}


@app.get("/api/costs")
def list_costs(db: Session = Depends(get_db)) -> list[dict]:
    costs = db.scalars(
        select(Cost)
        .where(Cost.farm_id == DEFAULT_FARM_ID)
        .options(selectinload(Cost.bed))
        .order_by(Cost.cost_date.desc(), Cost.id.desc())
    ).all()
    return [serialize_cost(cost) for cost in costs]


@app.post("/api/costs", status_code=status.HTTP_201_CREATED)
def create_cost(payload: CostCreate, db: Session = Depends(get_db)) -> dict:
    bed = db.get(Bed, payload.bed_id)
    if bed is None or bed.farm_id != DEFAULT_FARM_ID:
        raise HTTPException(status_code=404, detail="Gredica ne obstaja.")
    if payload.planting_id is not None:
        planting = db.get(Planting, payload.planting_id)
        if planting is None or planting.farm_id != DEFAULT_FARM_ID:
            raise HTTPException(status_code=404, detail="Setev ne obstaja.")
        if planting.bed_id != bed.id:
            raise HTTPException(status_code=422, detail="Setev ne pripada izbrani gredici.")
    cost = Cost(
        farm_id=DEFAULT_FARM_ID,
        bed_id=bed.id,
        planting_id=payload.planting_id,
        cost_date=payload.cost_date,
        category=payload.category,
        amount_eur=payload.amount_eur,
        description=payload.description.strip(),
    )
    db.add(cost)
    db.commit()
    db.refresh(cost)
    return {"message": "Strošek je zabeležen.", **serialize_cost(cost)}


@app.get("/api/sales")
def list_sales(db: Session = Depends(get_db)) -> list[dict]:
    sales = db.scalars(
        select(Sale)
        .where(Sale.farm_id == DEFAULT_FARM_ID)
        .options(selectinload(Sale.harvest).selectinload(Harvest.bed))
        .order_by(Sale.sale_date.desc(), Sale.id.desc())
    ).all()
    return [serialize_sale(sale) for sale in sales]


@app.post("/api/sales", status_code=status.HTTP_201_CREATED)
def create_sale(payload: SaleCreate, db: Session = Depends(get_db)) -> dict:
    harvest = db.scalar(
        select(Harvest)
        .where(Harvest.id == payload.harvest_id, Harvest.farm_id == DEFAULT_FARM_ID)
        .options(selectinload(Harvest.sales), selectinload(Harvest.bed))
    )
    if harvest is None:
        raise HTTPException(status_code=404, detail="Žetev ne obstaja.")
    already_sold = sum(sale.quantity_kg for sale in harvest.sales)
    reserved = reserved_quantity(db, harvest.id)
    if round(already_sold + reserved + payload.quantity_kg, 6) > round(harvest.quantity_kg, 6):
        raise HTTPException(
            status_code=409,
            detail="Prodana količina posega v prodano ali rezervirano zalogo žetve.",
        )
    sale = Sale(
        farm_id=DEFAULT_FARM_ID,
        harvest_id=harvest.id,
        sale_date=payload.sale_date,
        quantity_kg=payload.quantity_kg,
        price_per_kg_eur=payload.price_per_kg_eur,
        customer=payload.customer.strip() if payload.customer else None,
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return {"message": "Prodaja je zabeležena.", **serialize_sale(sale)}


@app.get("/api/economics/by-bed")
def economics_by_bed(db: Session = Depends(get_db)) -> list[dict]:
    beds = db.scalars(select(Bed).where(Bed.farm_id == DEFAULT_FARM_ID).order_by(Bed.name)).all()
    result = []
    for bed in beds:
        harvested_kg = db.scalar(
            select(func.coalesce(func.sum(Harvest.quantity_kg), 0.0)).where(Harvest.bed_id == bed.id)
        )
        costs_eur = db.scalar(
            select(func.coalesce(func.sum(Cost.amount_eur), 0.0)).where(Cost.bed_id == bed.id)
        )
        revenue_eur = db.scalar(
            select(func.coalesce(func.sum(Sale.quantity_kg * Sale.price_per_kg_eur), 0.0))
            .join(Harvest, Sale.harvest_id == Harvest.id)
            .where(Harvest.bed_id == bed.id)
        )
        result.append(
            {
                "bed_id": bed.id,
                "bed": bed.name,
                "area_m2": bed.area_m2,
                "harvested_kg": round(float(harvested_kg or 0), 2),
                "costs_eur": round(float(costs_eur or 0), 2),
                "revenue_eur": round(float(revenue_eur or 0), 2),
                "profit_eur": round(float(revenue_eur or 0) - float(costs_eur or 0), 2),
            }
        )
    return result


def reserved_quantity(db: Session, harvest_id: int, exclude_order_id: int | None = None) -> float:
    statement = (
        select(func.coalesce(func.sum(OrderItem.quantity_kg), 0.0))
        .join(Order, OrderItem.order_id == Order.id)
        .where(OrderItem.harvest_id == harvest_id, Order.status == "confirmed")
    )
    if exclude_order_id is not None:
        statement = statement.where(Order.id != exclude_order_id)
    return float(db.scalar(statement) or 0)


def sold_quantity(db: Session, harvest_id: int) -> float:
    return float(
        db.scalar(
            select(func.coalesce(func.sum(Sale.quantity_kg), 0.0)).where(
                Sale.harvest_id == harvest_id
            )
        )
        or 0
    )


def serialize_customer(customer: Customer) -> dict:
    profile = customer.profile
    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "address": customer.address,
        "notes": customer.notes,
        "customer_type": profile.customer_type if profile else "consumer",
        "tax_number": profile.tax_number if profile else None,
    }


def serialize_order(order: Order) -> dict:
    return {
        "id": order.id,
        "number": f"GM-{order.order_date.year}-{order.id:04d}",
        "customer_id": order.customer_id,
        "customer": order.customer.name,
        "customer_type": (
            order.customer.profile.customer_type if order.customer.profile else "consumer"
        ),
        "order_date": order.order_date,
        "delivery_date": order.delivery_date,
        "status": order.status,
        "notes": order.notes,
        "total_eur": order.total_eur,
        "items": [
            {
                "id": item.id,
                "harvest_id": item.harvest_id,
                "bed": item.harvest.bed.name,
                "crop": item.harvest.planting.crop.name,
                "variety": item.harvest.planting.variety.name,
                "quality": item.harvest.quality,
                "quantity_kg": item.quantity_kg,
                "price_per_kg_eur": item.price_per_kg_eur,
                "line_total_eur": item.line_total_eur,
            }
            for item in order.items
        ],
    }


def order_load_options() -> tuple:
    return (
        selectinload(Order.customer).selectinload(Customer.profile),
        selectinload(Order.items)
        .selectinload(OrderItem.harvest)
        .selectinload(Harvest.bed),
        selectinload(Order.items)
        .selectinload(OrderItem.harvest)
        .selectinload(Harvest.planting)
        .selectinload(Planting.crop),
        selectinload(Order.items)
        .selectinload(OrderItem.harvest)
        .selectinload(Harvest.planting)
        .selectinload(Planting.variety),
    )


@app.get("/api/inventory")
def inventory(db: Session = Depends(get_db)) -> list[dict]:
    harvests = db.scalars(
        select(Harvest)
        .where(Harvest.farm_id == DEFAULT_FARM_ID)
        .options(
            selectinload(Harvest.bed),
            selectinload(Harvest.planting).selectinload(Planting.crop),
            selectinload(Harvest.planting).selectinload(Planting.variety),
        )
        .order_by(Harvest.harvest_date.desc(), Harvest.id.desc())
    ).all()
    result = []
    for harvest in harvests:
        sold_kg = sold_quantity(db, harvest.id)
        reserved_kg = reserved_quantity(db, harvest.id)
        physical_kg = max(0.0, harvest.quantity_kg - sold_kg)
        available_kg = 0.0 if harvest.quality == "waste" else max(0.0, physical_kg - reserved_kg)
        result.append(
            {
                "harvest_id": harvest.id,
                "bed": harvest.bed.name,
                "crop": harvest.planting.crop.name,
                "variety": harvest.planting.variety.name,
                "harvest_date": harvest.harvest_date,
                "quality": harvest.quality,
                "harvested_kg": harvest.quantity_kg,
                "sold_kg": round(sold_kg, 2),
                "reserved_kg": round(reserved_kg, 2),
                "available_kg": round(available_kg, 2),
            }
        )
    return result


@app.get("/api/customers")
def list_customers(db: Session = Depends(get_db)) -> list[dict]:
    customers = db.scalars(
        select(Customer)
        .where(Customer.farm_id == DEFAULT_FARM_ID)
        .options(selectinload(Customer.profile))
        .order_by(Customer.name)
    ).all()
    return [serialize_customer(customer) for customer in customers]


@app.post("/api/customers", status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)) -> dict:
    name = payload.name.strip()
    duplicate = db.scalar(
        select(Customer).where(
            Customer.farm_id == DEFAULT_FARM_ID,
            func.lower(Customer.name) == name.lower(),
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Kupec s tem imenom že obstaja.")
    if payload.customer_type == "business" and not payload.tax_number:
        raise HTTPException(
            status_code=422,
            detail="Za poslovnega kupca vpišite davčno številko.",
        )
    customer = Customer(
        farm_id=DEFAULT_FARM_ID,
        name=name,
        email=payload.email.strip() if payload.email else None,
        phone=payload.phone.strip() if payload.phone else None,
        address=payload.address.strip() if payload.address else None,
        notes=payload.notes.strip() if payload.notes else None,
    )
    customer.profile = CustomerProfile(
        customer_type=payload.customer_type,
        tax_number=payload.tax_number.strip() if payload.tax_number else None,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return {"message": "Kupec je dodan.", **serialize_customer(customer)}


@app.get("/api/orders")
def list_orders(db: Session = Depends(get_db)) -> list[dict]:
    orders = db.scalars(
        select(Order)
        .where(Order.farm_id == DEFAULT_FARM_ID)
        .options(*order_load_options())
        .order_by(Order.delivery_date.desc(), Order.id.desc())
    ).all()
    return [serialize_order(order) for order in orders]


@app.post("/api/orders", status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)) -> dict:
    customer = db.get(Customer, payload.customer_id)
    if customer is None or customer.farm_id != DEFAULT_FARM_ID:
        raise HTTPException(status_code=404, detail="Kupec ne obstaja.")
    if payload.delivery_date < payload.order_date:
        raise HTTPException(status_code=422, detail="Datum dostave ne sme biti pred datumom naročila.")
    harvest_ids = [item.harvest_id for item in payload.items]
    if len(harvest_ids) != len(set(harvest_ids)):
        raise HTTPException(status_code=422, detail="Ista žetev je lahko v naročilu navedena samo enkrat.")

    harvests = {
        harvest.id: harvest
        for harvest in db.scalars(
            select(Harvest)
            .where(Harvest.id.in_(harvest_ids), Harvest.farm_id == DEFAULT_FARM_ID)
            .options(selectinload(Harvest.bed))
        ).all()
    }
    if len(harvests) != len(harvest_ids):
        raise HTTPException(status_code=404, detail="Ena ali več izbranih žetev ne obstaja.")
    for item in payload.items:
        harvest = harvests[item.harvest_id]
        if harvest.quality == "waste":
            raise HTTPException(status_code=409, detail="Odpadne kakovosti ni mogoče rezervirati za prodajo.")
        available = harvest.quantity_kg - sold_quantity(db, harvest.id) - reserved_quantity(db, harvest.id)
        if item.quantity_kg > round(available, 6):
            raise HTTPException(
                status_code=409,
                detail=f"Na gredici {harvest.bed.name} je na voljo le {max(0, round(available, 2))} kg.",
            )

    order = Order(
        farm_id=DEFAULT_FARM_ID,
        customer_id=customer.id,
        order_date=payload.order_date,
        delivery_date=payload.delivery_date,
        status="confirmed",
        notes=payload.notes.strip() if payload.notes else None,
    )
    order.items = [
        OrderItem(
            harvest_id=item.harvest_id,
            quantity_kg=item.quantity_kg,
            price_per_kg_eur=item.price_per_kg_eur,
        )
        for item in payload.items
    ]
    db.add(order)
    db.commit()
    order = db.scalar(select(Order).where(Order.id == order.id).options(*order_load_options()))
    return {"message": "Naročilo je potrjeno in količina rezervirana.", **serialize_order(order)}


@app.post("/api/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
) -> dict:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.farm_id == DEFAULT_FARM_ID)
        .options(*order_load_options())
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Naročilo ne obstaja.")
    if order.status != "confirmed":
        raise HTTPException(status_code=409, detail="Zaključeno ali preklicano naročilo se ne more več spremeniti.")

    if payload.status == "fulfilled":
        for item in order.items:
            available_physical = item.harvest.quantity_kg - sold_quantity(db, item.harvest_id)
            if item.quantity_kg > round(available_physical, 6):
                raise HTTPException(status_code=409, detail="Zaloga ne zadošča za zaključek naročila.")
            db.add(
                Sale(
                    farm_id=DEFAULT_FARM_ID,
                    harvest_id=item.harvest_id,
                    sale_date=order.delivery_date,
                    quantity_kg=item.quantity_kg,
                    price_per_kg_eur=item.price_per_kg_eur,
                    customer=order.customer.name,
                )
            )
    order.status = payload.status
    db.commit()
    order = db.scalar(select(Order).where(Order.id == order.id).options(*order_load_options()))
    message = "Naročilo je dostavljeno in prodaja zabeležena." if payload.status == "fulfilled" else "Naročilo je preklicano; zaloga je sproščena."
    return {"message": message, **serialize_order(order)}


@app.get("/api/orders/{order_id}/document")
def order_document(
    order_id: int,
    document_type: str = Query(default="delivery_note", pattern="^(delivery_note|invoice)$"),
    db: Session = Depends(get_db),
) -> dict:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.farm_id == DEFAULT_FARM_ID)
        .options(*order_load_options())
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Naročilo ne obstaja.")
    if document_type == "invoice":
        if order.status != "fulfilled":
            raise HTTPException(status_code=409, detail="Račun je na voljo po dostavi naročila.")
        customer_type = (
            order.customer.profile.customer_type if order.customer.profile else "consumer"
        )
        settings = get_sales_settings(db)
        if customer_type == "consumer" and settings.basic_agriculture_invoice_exemption:
            raise HTTPException(
                status_code=409,
                detail="Za končnega potrošnika ob vključeni izjemi 81.a račun ni predviden.",
            )
    return {
        "document_type": document_type,
        "document_number": ("R" if document_type == "invoice" else "D") + f"-{order.order_date.year}-{order.id:04d}",
        "order": serialize_order(order),
        "customer": serialize_customer(order.customer),
        "issued_on": date.today(),
    }


def serialize_crop_plan(plan: CropPlan) -> dict:
    return {
        "id": plan.id,
        "series_id": plan.series_id,
        "bed_id": plan.bed_id,
        "bed": plan.bed.name,
        "crop_id": plan.crop_id,
        "crop": plan.crop.name,
        "variety_id": plan.variety_id,
        "variety": plan.variety.name,
        "sowing_date": plan.sowing_date,
        "transplant_date": plan.transplant_date,
        "expected_harvest_date": plan.expected_harvest_date,
        "expected_yield_kg": plan.expected_yield_kg,
        "status": plan.status,
        "planting_id": plan.planting_id,
        "notes": plan.notes,
    }


def crop_plan_options() -> tuple:
    return (
        selectinload(CropPlan.bed),
        selectinload(CropPlan.crop),
        selectinload(CropPlan.variety),
    )


@app.get("/api/plans")
def list_crop_plans(
    include_cancelled: bool = False,
    db: Session = Depends(get_db),
) -> list[dict]:
    statement = (
        select(CropPlan)
        .where(CropPlan.farm_id == DEFAULT_FARM_ID)
        .options(*crop_plan_options())
        .order_by(CropPlan.sowing_date, CropPlan.id)
    )
    if not include_cancelled:
        statement = statement.where(CropPlan.status != "cancelled")
    return [serialize_crop_plan(plan) for plan in db.scalars(statement).all()]


@app.post("/api/plans", status_code=status.HTTP_201_CREATED)
def create_crop_plan(payload: CropPlanCreate, db: Session = Depends(get_db)) -> dict:
    bed = db.get(Bed, payload.bed_id)
    crop = db.get(Crop, payload.crop_id)
    variety = db.get(Variety, payload.variety_id)
    if bed is None or crop is None or variety is None:
        raise HTTPException(status_code=404, detail="Gredica, kultura ali sorta ne obstaja.")
    if bed.farm_id != DEFAULT_FARM_ID:
        raise HTTPException(status_code=403, detail="Gredica ne pripada aktivni kmetiji.")
    if variety.crop_id != crop.id:
        raise HTTPException(status_code=422, detail="Sorta ne pripada izbrani kulturi.")
    if payload.transplant_date and payload.transplant_date < payload.sowing_date:
        raise HTTPException(status_code=422, detail="Presajanje ne sme biti pred setvijo.")

    existing = db.scalars(
        select(CropPlan)
        .where(
            CropPlan.bed_id == bed.id,
            CropPlan.status == "planned",
        )
        .options(*crop_plan_options())
    ).all()
    active = active_planting_for_bed(db, bed.id)
    series_id = str(uuid4())
    created: list[CropPlan] = []
    warnings: list[str] = []
    for index in range(payload.succession_count):
        offset = timedelta(days=index * payload.succession_interval_days)
        sowing_date = payload.sowing_date + offset
        harvest_date = sowing_date + timedelta(days=variety.days_to_harvest)
        transplant_date = payload.transplant_date + offset if payload.transplant_date else None
        overlaps = [
            other
            for other in [*existing, *created]
            if other.sowing_date <= harvest_date and other.expected_harvest_date >= sowing_date
        ]
        if overlaps:
            warnings.append(
                f"{sowing_date}: gredica {bed.name} se časovno prekriva z drugim načrtom."
            )
        if active is not None and index == 0:
            warnings.append(f"Gredica {bed.name} je trenutno zasedena z aktivno setvijo.")
        plan = CropPlan(
            farm_id=DEFAULT_FARM_ID,
            bed_id=bed.id,
            crop_id=crop.id,
            variety_id=variety.id,
            series_id=series_id,
            sowing_date=sowing_date,
            transplant_date=transplant_date,
            expected_harvest_date=harvest_date,
            expected_yield_kg=payload.expected_yield_kg,
            status="planned",
            notes=payload.notes.strip() if payload.notes else None,
        )
        plan.bed = bed
        plan.crop = crop
        plan.variety = variety
        db.add(plan)
        created.append(plan)
    db.commit()
    return {
        "message": f"Ustvarjenih je {len(created)} načrtovanih setev.",
        "series_id": series_id,
        "warnings": warnings,
        "plans": [serialize_crop_plan(plan) for plan in created],
    }


@app.post("/api/plans/{plan_id}/activate")
def activate_crop_plan(
    plan_id: int,
    payload: CropPlanActivate,
    db: Session = Depends(get_db),
) -> dict:
    plan = db.scalar(
        select(CropPlan)
        .where(CropPlan.id == plan_id, CropPlan.farm_id == DEFAULT_FARM_ID)
        .options(*crop_plan_options())
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Načrt ne obstaja.")
    if plan.status != "planned":
        raise HTTPException(status_code=409, detail="Aktivirati je mogoče le načrtovano setev.")
    planting_payload = PlantingCreate(
        crop_id=plan.crop_id,
        variety_id=plan.variety_id,
        bed_id=plan.bed_id,
        sowing_date=plan.sowing_date,
        override_rotation=payload.override_rotation,
    )
    preview = rotation_preview(planting_payload, db)
    if not preview.allowed or (preview.requires_override and not payload.override_rotation):
        raise HTTPException(status_code=409, detail=preview.model_dump())
    planting = Planting(
        farm_id=DEFAULT_FARM_ID,
        bed_id=plan.bed_id,
        crop_id=plan.crop_id,
        variety_id=plan.variety_id,
        sowing_date=plan.sowing_date,
        expected_harvest_date=plan.expected_harvest_date,
        rotation_override=payload.override_rotation,
        status="active",
    )
    plan.bed.status = "growing"
    db.add(planting)
    db.flush()
    planting.crop = plan.crop
    planting.variety = plan.variety
    add_automatic_tasks(db, planting, plan.bed)
    plan.status = "activated"
    plan.planting_id = planting.id
    db.commit()
    return {
        "message": f"Načrt za {plan.crop.name} na gredici {plan.bed.name} je aktiviran.",
        "planting_id": planting.id,
        "plan": serialize_crop_plan(plan),
    }


@app.post("/api/plans/{plan_id}/status")
def update_crop_plan_status(
    plan_id: int,
    payload: CropPlanStatusUpdate,
    db: Session = Depends(get_db),
) -> dict:
    plan = db.scalar(
        select(CropPlan)
        .where(CropPlan.id == plan_id, CropPlan.farm_id == DEFAULT_FARM_ID)
        .options(*crop_plan_options())
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Načrt ne obstaja.")
    if plan.status != "planned":
        raise HTTPException(status_code=409, detail="Spremeniti je mogoče le načrtovano setev.")
    plan.status = payload.status
    db.commit()
    return {"message": "Načrt je preklican.", **serialize_crop_plan(plan)}


def planning_range(start: date | None, end: date | None) -> tuple[date, date]:
    range_start = start or date.today()
    range_end = end or range_start + timedelta(days=90)
    if range_end < range_start:
        raise HTTPException(status_code=422, detail="Konec obdobja ne sme biti pred začetkom.")
    return range_start, range_end


@app.get("/api/planning/calendar")
def planning_calendar(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> dict:
    range_start, range_end = planning_range(start, end)
    events: list[dict] = []
    plans = db.scalars(
        select(CropPlan)
        .where(
            CropPlan.farm_id == DEFAULT_FARM_ID,
            CropPlan.status == "planned",
            CropPlan.sowing_date <= range_end,
            CropPlan.expected_harvest_date >= range_start,
        )
        .options(*crop_plan_options())
    ).all()
    for plan in plans:
        candidates = [
            (plan.sowing_date, "sowing", "Setev"),
            (plan.transplant_date, "transplant", "Presajanje"),
            (plan.expected_harvest_date, "planned_harvest", "Predvidena žetev"),
        ]
        for event_date, event_type, label in candidates:
            if event_date and range_start <= event_date <= range_end:
                events.append(
                    {
                        "date": event_date,
                        "type": event_type,
                        "title": f"{label}: {plan.crop.name} {plan.variety.name}",
                        "bed": plan.bed.name,
                        "plan_id": plan.id,
                    }
                )
    tasks = db.scalars(
        select(Task)
        .where(
            Task.farm_id == DEFAULT_FARM_ID,
            Task.due_date >= range_start,
            Task.due_date <= range_end,
            Task.status == "planned",
        )
        .options(selectinload(Task.bed))
    ).all()
    events.extend(
        {
            "date": task.due_date,
            "type": "task",
            "title": task.title,
            "bed": task.bed.name if task.bed else None,
            "task_id": task.id,
        }
        for task in tasks
    )
    orders = db.scalars(
        select(Order)
        .where(
            Order.farm_id == DEFAULT_FARM_ID,
            Order.delivery_date >= range_start,
            Order.delivery_date <= range_end,
            Order.status == "confirmed",
        )
        .options(selectinload(Order.customer))
    ).all()
    events.extend(
        {
            "date": order.delivery_date,
            "type": "delivery",
            "title": f"Dostava: {order.customer.name}",
            "bed": None,
            "order_id": order.id,
        }
        for order in orders
    )
    events.sort(key=lambda event: (event["date"], event["type"], event["title"]))
    return {"start": range_start, "end": range_end, "events": events}


@app.get("/api/planning/forecast")
def planning_forecast(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> dict:
    range_start, range_end = planning_range(start, end)
    crops = db.scalars(select(Crop).order_by(Crop.name)).all()
    harvests = db.scalars(
        select(Harvest)
        .where(Harvest.farm_id == DEFAULT_FARM_ID, Harvest.quality != "waste")
        .options(selectinload(Harvest.planting).selectinload(Planting.crop))
    ).all()
    plans = db.scalars(
        select(CropPlan)
        .where(
            CropPlan.farm_id == DEFAULT_FARM_ID,
            CropPlan.status == "planned",
            CropPlan.expected_harvest_date >= range_start,
            CropPlan.expected_harvest_date <= range_end,
        )
    ).all()
    orders = db.scalars(
        select(Order)
        .where(
            Order.farm_id == DEFAULT_FARM_ID,
            Order.status == "confirmed",
            Order.delivery_date >= range_start,
            Order.delivery_date <= range_end,
        )
        .options(
            selectinload(Order.items)
            .selectinload(OrderItem.harvest)
            .selectinload(Harvest.planting)
            .selectinload(Planting.crop)
        )
    ).all()
    rows = []
    for crop in crops:
        current_stock = sum(
            max(0.0, harvest.quantity_kg - sold_quantity(db, harvest.id))
            for harvest in harvests
            if harvest.planting.crop_id == crop.id
        )
        planned_yield = sum(plan.expected_yield_kg for plan in plans if plan.crop_id == crop.id)
        demand = sum(
            item.quantity_kg
            for order in orders
            for item in order.items
            if item.harvest.planting.crop_id == crop.id
        )
        if current_stock or planned_yield or demand:
            projected = current_stock + planned_yield - demand
            rows.append(
                {
                    "crop_id": crop.id,
                    "crop": crop.name,
                    "current_stock_kg": round(current_stock, 2),
                    "planned_yield_kg": round(planned_yield, 2),
                    "confirmed_demand_kg": round(demand, 2),
                    "projected_balance_kg": round(projected, 2),
                    "shortage": projected < 0,
                }
            )
    return {
        "start": range_start,
        "end": range_end,
        "rows": rows,
        "warnings": [
            f"Za kulturo {row['crop']} manjka {abs(row['projected_balance_kg'])} kg."
            for row in rows
            if row["shortage"]
        ],
    }


def get_sales_settings(db: Session) -> SalesSettings:
    settings = db.get(SalesSettings, DEFAULT_FARM_ID)
    if settings is None:
        settings = SalesSettings(
            farm_id=DEFAULT_FARM_ID,
            basic_agriculture_invoice_exemption=True,
            seller_name="GrowMaster kmetija",
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def retail_sale_options() -> tuple:
    return (
        selectinload(RetailSale.customer).selectinload(Customer.profile),
        selectinload(RetailSale.items)
        .selectinload(RetailSaleItem.harvest)
        .selectinload(Harvest.bed),
        selectinload(RetailSale.items)
        .selectinload(RetailSaleItem.harvest)
        .selectinload(Harvest.planting)
        .selectinload(Planting.crop),
        selectinload(RetailSale.items)
        .selectinload(RetailSaleItem.harvest)
        .selectinload(Harvest.planting)
        .selectinload(Planting.variety),
    )


def retail_sale_requires_invoice(retail_sale: RetailSale, settings: SalesSettings) -> bool:
    customer_type = (
        retail_sale.customer.profile.customer_type
        if retail_sale.customer and retail_sale.customer.profile
        else "consumer"
    )
    return customer_type == "business" or not settings.basic_agriculture_invoice_exemption


def serialize_retail_sale(retail_sale: RetailSale, settings: SalesSettings) -> dict:
    customer_type = (
        retail_sale.customer.profile.customer_type
        if retail_sale.customer and retail_sale.customer.profile
        else "consumer"
    )
    return {
        "id": retail_sale.id,
        "number": f"MP-{retail_sale.sale_date.year}-{retail_sale.id:04d}",
        "sale_date": retail_sale.sale_date,
        "payment_method": retail_sale.payment_method,
        "customer_id": retail_sale.customer_id,
        "customer": retail_sale.customer.name if retail_sale.customer else "Končni potrošnik",
        "customer_type": customer_type,
        "invoice_required": retail_sale_requires_invoice(retail_sale, settings),
        "notes": retail_sale.notes,
        "total_eur": retail_sale.total_eur,
        "items": [
            {
                "id": item.id,
                "harvest_id": item.harvest_id,
                "crop": item.harvest.planting.crop.name,
                "variety": item.harvest.planting.variety.name,
                "bed": item.harvest.bed.name,
                "quantity_kg": item.quantity_kg,
                "price_per_kg_eur": item.price_per_kg_eur,
                "line_total_eur": item.line_total_eur,
            }
            for item in retail_sale.items
        ],
    }


@app.get("/api/sales-settings")
def sales_settings(db: Session = Depends(get_db)) -> dict:
    settings = get_sales_settings(db)
    return {
        "basic_agriculture_invoice_exemption": settings.basic_agriculture_invoice_exemption,
        "seller_name": settings.seller_name,
        "seller_tax_number": settings.seller_tax_number,
        "legal_basis": "Izjema za neposredno prodajo lastnih pridelkov končnemu potrošniku po 81.a členu ZDDV-1.",
    }


@app.put("/api/sales-settings")
def update_sales_settings(
    payload: SalesSettingsUpdate,
    db: Session = Depends(get_db),
) -> dict:
    settings = get_sales_settings(db)
    settings.basic_agriculture_invoice_exemption = (
        payload.basic_agriculture_invoice_exemption
    )
    settings.seller_name = payload.seller_name.strip()
    settings.seller_tax_number = (
        payload.seller_tax_number.strip() if payload.seller_tax_number else None
    )
    db.commit()
    return {"message": "Nastavitve prodaje so shranjene.", **sales_settings(db)}


@app.get("/api/retail-sales")
def list_retail_sales(db: Session = Depends(get_db)) -> list[dict]:
    settings = get_sales_settings(db)
    retail_sales = db.scalars(
        select(RetailSale)
        .where(RetailSale.farm_id == DEFAULT_FARM_ID)
        .options(*retail_sale_options())
        .order_by(RetailSale.sale_date.desc(), RetailSale.id.desc())
    ).all()
    return [serialize_retail_sale(retail_sale, settings) for retail_sale in retail_sales]


@app.post("/api/retail-sales", status_code=status.HTTP_201_CREATED)
def create_retail_sale(
    payload: RetailSaleCreate,
    db: Session = Depends(get_db),
) -> dict:
    customer = None
    if payload.customer_id is not None:
        customer = db.scalar(
            select(Customer)
            .where(
                Customer.id == payload.customer_id,
                Customer.farm_id == DEFAULT_FARM_ID,
            )
            .options(selectinload(Customer.profile))
        )
        if customer is None:
            raise HTTPException(status_code=404, detail="Kupec ne obstaja.")
    harvest_ids = [item.harvest_id for item in payload.items]
    if len(harvest_ids) != len(set(harvest_ids)):
        raise HTTPException(status_code=422, detail="Ista žetev je lahko navedena samo enkrat.")
    harvests = {
        harvest.id: harvest
        for harvest in db.scalars(
            select(Harvest)
            .where(Harvest.id.in_(harvest_ids), Harvest.farm_id == DEFAULT_FARM_ID)
            .options(
                selectinload(Harvest.bed),
                selectinload(Harvest.planting).selectinload(Planting.crop),
                selectinload(Harvest.planting).selectinload(Planting.variety),
            )
        ).all()
    }
    if len(harvests) != len(harvest_ids):
        raise HTTPException(status_code=404, detail="Ena ali več izbranih žetev ne obstaja.")
    for item in payload.items:
        harvest = harvests[item.harvest_id]
        if harvest.quality == "waste":
            raise HTTPException(status_code=409, detail="Odpadne kakovosti ni mogoče prodati.")
        available = harvest.quantity_kg - sold_quantity(db, harvest.id) - reserved_quantity(db, harvest.id)
        if item.quantity_kg > round(available, 6):
            raise HTTPException(
                status_code=409,
                detail=f"Na gredici {harvest.bed.name} je na voljo le {max(0, round(available, 2))} kg.",
            )
    retail_sale = RetailSale(
        farm_id=DEFAULT_FARM_ID,
        customer_id=customer.id if customer else None,
        sale_date=payload.sale_date,
        payment_method=payload.payment_method,
        notes=payload.notes.strip() if payload.notes else None,
    )
    retail_sale.items = [
        RetailSaleItem(
            harvest_id=item.harvest_id,
            quantity_kg=item.quantity_kg,
            price_per_kg_eur=item.price_per_kg_eur,
        )
        for item in payload.items
    ]
    db.add(retail_sale)
    for item in payload.items:
        db.add(
            Sale(
                farm_id=DEFAULT_FARM_ID,
                harvest_id=item.harvest_id,
                sale_date=payload.sale_date,
                quantity_kg=item.quantity_kg,
                price_per_kg_eur=item.price_per_kg_eur,
                customer=customer.name if customer else "Končni potrošnik",
            )
        )
    db.commit()
    retail_sale = db.scalar(
        select(RetailSale)
        .where(RetailSale.id == retail_sale.id)
        .options(*retail_sale_options())
    )
    settings = get_sales_settings(db)
    return {
        "message": "Hitra prodaja je zabeležena in zaloga posodobljena.",
        **serialize_retail_sale(retail_sale, settings),
    }


@app.get("/api/retail-sales/{retail_sale_id}/document")
def retail_sale_document(
    retail_sale_id: int,
    document_type: str = Query(default="receipt", pattern="^(receipt|invoice)$"),
    db: Session = Depends(get_db),
) -> dict:
    retail_sale = db.scalar(
        select(RetailSale)
        .where(
            RetailSale.id == retail_sale_id,
            RetailSale.farm_id == DEFAULT_FARM_ID,
        )
        .options(*retail_sale_options())
    )
    if retail_sale is None:
        raise HTTPException(status_code=404, detail="Prodaja ne obstaja.")
    settings = get_sales_settings(db)
    invoice_required = retail_sale_requires_invoice(retail_sale, settings)
    if document_type == "invoice" and not invoice_required:
        raise HTTPException(
            status_code=409,
            detail="Za to prodajo končnemu potrošniku račun ni predviden.",
        )
    return {
        "document_type": document_type,
        "document_number": (
            ("R" if document_type == "invoice" else "P")
            + f"-{retail_sale.sale_date.year}-{retail_sale.id:04d}"
        ),
        "seller": {
            "name": settings.seller_name,
            "tax_number": settings.seller_tax_number,
        },
        "sale": serialize_retail_sale(retail_sale, settings),
        "fiscal_confirmation_required": (
            document_type == "invoice"
            and retail_sale.payment_method in {"cash", "card"}
        ),
        "issued_on": date.today(),
    }


def sales_report_range(start: date | None, end: date | None) -> tuple[date, date]:
    range_start = start or date.today()
    range_end = end or range_start
    if range_end < range_start:
        raise HTTPException(status_code=422, detail="Konec obdobja ne sme biti pred začetkom.")
    return range_start, range_end


def build_sales_report(db: Session, start: date | None, end: date | None) -> dict:
    range_start, range_end = sales_report_range(start, end)
    settings = get_sales_settings(db)
    retail_sales = db.scalars(
        select(RetailSale)
        .where(
            RetailSale.farm_id == DEFAULT_FARM_ID,
            RetailSale.sale_date >= range_start,
            RetailSale.sale_date <= range_end,
        )
        .options(*retail_sale_options())
    ).all()
    orders = db.scalars(
        select(Order)
        .where(
            Order.farm_id == DEFAULT_FARM_ID,
            Order.status == "fulfilled",
            Order.delivery_date >= range_start,
            Order.delivery_date <= range_end,
        )
        .options(*order_load_options())
    ).all()

    entries = []
    for retail_sale in retail_sales:
        serialized = serialize_retail_sale(retail_sale, settings)
        entries.append(
            {
                "key": f"retail-{retail_sale.id}",
                "source": "retail_sale",
                "number": serialized["number"],
                "date": retail_sale.sale_date,
                "customer": serialized["customer"],
                "customer_type": serialized["customer_type"],
                "payment_method": retail_sale.payment_method,
                "total_eur": retail_sale.total_eur,
                "invoice_required": serialized["invoice_required"],
            }
        )
    for order in orders:
        customer_type = order.customer.profile.customer_type if order.customer.profile else "consumer"
        invoice_required = (
            customer_type == "business"
            or not settings.basic_agriculture_invoice_exemption
        )
        entries.append(
            {
                "key": f"order-{order.id}",
                "source": "order",
                "number": f"GM-{order.order_date.year}-{order.id:04d}",
                "date": order.delivery_date,
                "customer": order.customer.name,
                "customer_type": customer_type,
                "payment_method": "invoice" if invoice_required else "unclassified",
                "total_eur": order.total_eur,
                "invoice_required": invoice_required,
            }
        )
    entries.sort(key=lambda entry: (entry["date"], entry["key"]), reverse=True)

    payment_keys = ("cash", "card", "bank_transfer", "invoice", "unclassified")
    summary = {
        "transactions": len(entries),
        "total_eur": round(sum(entry["total_eur"] for entry in entries), 2),
        **{
            f"{payment_method}_eur": round(
                sum(
                    entry["total_eur"]
                    for entry in entries
                    if entry["payment_method"] == payment_method
                ),
                2,
            )
            for payment_method in payment_keys
        },
        "invoice_eur": round(
            sum(entry["total_eur"] for entry in entries if entry["invoice_required"]),
            2,
        ),
        "consumer_eur": round(
            sum(entry["total_eur"] for entry in entries if entry["customer_type"] == "consumer"),
            2,
        ),
        "business_eur": round(
            sum(entry["total_eur"] for entry in entries if entry["customer_type"] == "business"),
            2,
        ),
        "invoice_count": sum(entry["invoice_required"] for entry in entries),
    }
    daily = []
    for report_date in sorted({entry["date"] for entry in entries}, reverse=True):
        day_entries = [entry for entry in entries if entry["date"] == report_date]
        daily.append(
            {
                "date": report_date,
                "transactions": len(day_entries),
                "total_eur": round(sum(entry["total_eur"] for entry in day_entries), 2),
                **{
                    f"{payment_method}_eur": round(
                        sum(
                            entry["total_eur"]
                            for entry in day_entries
                            if entry["payment_method"] == payment_method
                        ),
                        2,
                    )
                    for payment_method in payment_keys
                },
                "invoice_eur": round(
                    sum(
                        entry["total_eur"]
                        for entry in day_entries
                        if entry["invoice_required"]
                    ),
                    2,
                ),
            }
        )
    return {
        "start": range_start,
        "end": range_end,
        "summary": summary,
        "daily": daily,
        "entries": entries,
        "note": (
            "Register vključuje hitre prodaje in dostavljena naročila. "
            "Izdani računi so prikazani ločeno; njihovo plačilo s tem ni samodejno potrjeno."
        ),
    }


@app.get("/api/sales-report")
def sales_report(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> dict:
    return build_sales_report(db, start, end)


@app.get("/api/sales-report/export.csv")
def export_sales_report(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> Response:
    report = build_sales_report(db, start, end)

    def spreadsheet_cell(value: object) -> str:
        text = str(value)
        return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "Datum",
            "Številka",
            "Vrsta",
            "Kupec",
            "Tip kupca",
            "Način plačila",
            "Znesek EUR",
            "Račun potreben",
        ]
    )
    for entry in report["entries"]:
        writer.writerow(
            [
                entry["date"].isoformat(),
                spreadsheet_cell(entry["number"]),
                spreadsheet_cell(entry["source"]),
                spreadsheet_cell(entry["customer"]),
                spreadsheet_cell(entry["customer_type"]),
                spreadsheet_cell(entry["payment_method"]),
                f'{entry["total_eur"]:.2f}',
                "da" if entry["invoice_required"] else "ne",
            ]
        )
    filename = f'growmaster-prodaja-{report["start"]}-{report["end"]}.csv'
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
