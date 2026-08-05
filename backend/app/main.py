import csv
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import hashlib
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
    CreditNote,
    DayClose,
    DayCloseSupplierPaymentSnapshot,
    DocumentSequence,
    Farm,
    Harvest,
    Invoice,
    InvoiceLine,
    InvoiceProfile,
    Order,
    OrderItem,
    OrderPayment,
    Planting,
    ProductPrice,
    PurchaseOrder,
    PurchaseOrderItem,
    RetailSale,
    RetailSaleItem,
    Refund,
    Sale,
    SalesSettings,
    Supplier,
    SupplierPayment,
    SupplyItem,
    SupplyUsage,
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
    CreditNoteCreate,
    DayCloseCreate,
    FiscalConfirmationCreate,
    HarvestCreate,
    InvoiceCreate,
    InvoiceProfileUpdate,
    OrderCreate,
    OrderPaymentCreate,
    OrderStatusUpdate,
    ProductPriceUpdate,
    PurchaseOrderCreate,
    PurchaseOrderReceive,
    RetailSaleCreate,
    RefundCreate,
    PlantingCreate,
    RotationPreview,
    SaleCreate,
    SalesSettingsUpdate,
    SupplierCreate,
    SupplierPaymentCreate,
    SupplyItemCreate,
    SupplyUsageCreate,
    TaskComplete,
    TaskCreate,
)
from app.seed import seed_database
from app.invoice_pdf import build_invoice_pdf

DEFAULT_FARM_ID = 1


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(title="GrowMaster API", version="1.5.0", lifespan=lifespan)
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
        direct_costs_eur = db.scalar(
            select(func.coalesce(func.sum(Cost.amount_eur), 0.0)).where(Cost.bed_id == bed.id)
        )
        material_costs_eur = db.scalar(
            select(
                func.coalesce(
                    func.sum(SupplyUsage.quantity * SupplyUsage.unit_cost_eur),
                    0.0,
                )
            ).where(SupplyUsage.bed_id == bed.id)
        )
        costs_eur = float(direct_costs_eur or 0) + float(material_costs_eur or 0)
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
                "direct_costs_eur": round(float(direct_costs_eur or 0), 2),
                "material_costs_eur": round(float(material_costs_eur or 0), 2),
                "costs_eur": round(costs_eur, 2),
                "revenue_eur": round(float(revenue_eur or 0), 2),
                "profit_eur": round(float(revenue_eur or 0) - costs_eur, 2),
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


def invoice_summary(invoice: Invoice | None) -> dict | None:
    if invoice is None:
        return None
    return {
        "id": invoice.id,
        "number": invoice.number,
        "status": invoice.status,
        "fiscal_status": fiscal_status(
            invoice.fiscal_confirmation_required, invoice.eor
        ),
        "credit_note_id": invoice.credit_note.id if invoice.credit_note else None,
    }


def serialize_order(order: Order) -> dict:
    paid_eur = round(sum(payment.amount_eur for payment in order.payments), 2)
    outstanding_eur = round(max(0.0, order.total_eur - paid_eur), 2)
    payment_status = (
        "paid"
        if order.status == "fulfilled" and outstanding_eur <= 0
        else "partial"
        if paid_eur > 0
        else "open"
        if order.status == "fulfilled"
        else "pending"
    )
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
        "paid_eur": paid_eur,
        "outstanding_eur": outstanding_eur,
        "payment_status": payment_status,
        "invoice": invoice_summary(order.invoice),
        "payments": [
            {
                "id": payment.id,
                "payment_date": payment.payment_date,
                "amount_eur": payment.amount_eur,
                "payment_method": payment.payment_method,
                "notes": payment.notes,
            }
            for payment in sorted(order.payments, key=lambda item: (item.payment_date, item.id))
        ],
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
        selectinload(Order.payments),
        selectinload(Order.invoice).selectinload(Invoice.credit_note),
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


def serialize_product_price(price: ProductPrice) -> dict:
    return {
        "id": price.id,
        "crop_id": price.crop_id,
        "crop": price.crop.name,
        "quality": price.quality,
        "price_per_kg_eur": price.price_per_kg_eur,
        "updated_at": price.updated_at,
    }


@app.get("/api/price-list")
def price_list(db: Session = Depends(get_db)) -> list[dict]:
    prices = db.scalars(
        select(ProductPrice)
        .where(ProductPrice.farm_id == DEFAULT_FARM_ID)
        .join(ProductPrice.crop)
        .options(selectinload(ProductPrice.crop))
        .order_by(Crop.name, ProductPrice.quality)
    ).all()
    return [serialize_product_price(price) for price in prices]


@app.put("/api/price-list/{crop_id}")
def update_product_price(
    crop_id: int,
    payload: ProductPriceUpdate,
    db: Session = Depends(get_db),
) -> dict:
    crop = db.get(Crop, crop_id)
    if crop is None:
        raise HTTPException(status_code=404, detail="Kultura ne obstaja.")
    price = db.scalar(
        select(ProductPrice)
        .where(
            ProductPrice.farm_id == DEFAULT_FARM_ID,
            ProductPrice.crop_id == crop.id,
            ProductPrice.quality == payload.quality,
        )
        .options(selectinload(ProductPrice.crop))
        .with_for_update()
    )
    if price is None:
        price = ProductPrice(
            farm_id=DEFAULT_FARM_ID,
            crop_id=crop.id,
            quality=payload.quality,
            price_per_kg_eur=round(payload.price_per_kg_eur, 2),
        )
        price.crop = crop
        db.add(price)
    else:
        price.price_per_kg_eur = round(payload.price_per_kg_eur, 2)
    db.commit()
    db.refresh(price)
    return {
        "message": "Prodajna cena je shranjena.",
        **serialize_product_price(price),
    }


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
    prices = {
        (price.crop_id, price.quality): price.price_per_kg_eur
        for price in db.scalars(
            select(ProductPrice).where(ProductPrice.farm_id == DEFAULT_FARM_ID)
        ).all()
    }
    result = []
    for harvest in harvests:
        sold_kg = sold_quantity(db, harvest.id)
        reserved_kg = reserved_quantity(db, harvest.id)
        physical_kg = max(0.0, harvest.quantity_kg - sold_kg)
        available_kg = 0.0 if harvest.quality == "waste" else max(0.0, physical_kg - reserved_kg)
        result.append(
            {
                "harvest_id": harvest.id,
                "crop_id": harvest.planting.crop_id,
                "bed": harvest.bed.name,
                "crop": harvest.planting.crop.name,
                "variety": harvest.planting.variety.name,
                "harvest_date": harvest.harvest_date,
                "quality": harvest.quality,
                "harvested_kg": harvest.quantity_kg,
                "sold_kg": round(sold_kg, 2),
                "reserved_kg": round(reserved_kg, 2),
                "available_kg": round(available_kg, 2),
                "suggested_price_per_kg_eur": prices.get(
                    (harvest.planting.crop_id, harvest.quality)
                ),
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
        settings = get_sales_settings(db)
        if not order_requires_invoice(order, settings):
            raise HTTPException(
                status_code=409,
                detail="Za končnega potrošnika ob vključeni izjemi 81.a račun ni predviden.",
            )
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Sprotni račun je ukinjen. Izdajte nespremenljiv račun prek /api/invoices.",
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
        selectinload(RetailSale.invoice).selectinload(Invoice.credit_note),
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


def order_requires_invoice(order: Order, settings: SalesSettings) -> bool:
    customer_type = order.customer.profile.customer_type if order.customer.profile else "consumer"
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
        "invoice": invoice_summary(retail_sale.invoice),
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


def get_invoice_profile(db: Session) -> InvoiceProfile:
    profile = db.get(InvoiceProfile, DEFAULT_FARM_ID)
    if profile is None:
        profile = InvoiceProfile(farm_id=DEFAULT_FARM_ID)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def serialize_invoice_profile(profile: InvoiceProfile) -> dict:
    return {
        "seller_address": profile.seller_address,
        "seller_iban": profile.seller_iban,
        "seller_registration_number": profile.seller_registration_number,
        "vat_note": profile.vat_note,
        "business_premise_code": profile.business_premise_code,
        "device_code": profile.device_code,
        "default_due_days": profile.default_due_days,
    }


@app.get("/api/invoice-profile")
def invoice_profile(db: Session = Depends(get_db)) -> dict:
    return serialize_invoice_profile(get_invoice_profile(db))


@app.put("/api/invoice-profile")
def update_invoice_profile(
    payload: InvoiceProfileUpdate,
    db: Session = Depends(get_db),
) -> dict:
    profile = get_invoice_profile(db)
    profile.seller_address = payload.seller_address.strip()
    profile.seller_iban = payload.seller_iban.strip() if payload.seller_iban else None
    profile.seller_registration_number = (
        payload.seller_registration_number.strip()
        if payload.seller_registration_number
        else None
    )
    profile.vat_note = payload.vat_note.strip() if payload.vat_note else None
    profile.business_premise_code = payload.business_premise_code.strip().upper()
    profile.device_code = payload.device_code.strip().upper()
    profile.default_due_days = payload.default_due_days
    db.commit()
    return {
        "message": "Podatki za račune so shranjeni.",
        **serialize_invoice_profile(profile),
    }


def next_document_number(
    db: Session,
    issued_on: date,
    document_type: str,
    profile: InvoiceProfile,
) -> str:
    # Lock the farm row so even creation of a new yearly sequence is serialized.
    db.scalar(
        select(Farm.id).where(Farm.id == DEFAULT_FARM_ID).with_for_update()
    )
    sequence = db.scalar(
        select(DocumentSequence)
        .where(
            DocumentSequence.farm_id == DEFAULT_FARM_ID,
            DocumentSequence.year == issued_on.year,
            DocumentSequence.document_type == document_type,
        )
        .with_for_update()
    )
    if sequence is None:
        sequence = DocumentSequence(
            farm_id=DEFAULT_FARM_ID,
            year=issued_on.year,
            document_type=document_type,
            next_number=1,
        )
        db.add(sequence)
        db.flush()
    ordinal = sequence.next_number
    sequence.next_number += 1
    prefix = "R" if document_type == "invoice" else "DB"
    return (
        f"{prefix}-{profile.business_premise_code}-{profile.device_code}-"
        f"{issued_on.year}-{ordinal:04d}"
    )


def invoice_load_options() -> tuple:
    return (
        selectinload(Invoice.lines),
        selectinload(Invoice.credit_note).selectinload(CreditNote.refunds),
        selectinload(Invoice.order).selectinload(Order.payments),
    )


def credit_note_load_options() -> tuple:
    return (
        selectinload(CreditNote.refunds),
        selectinload(CreditNote.invoice).selectinload(Invoice.lines),
        selectinload(CreditNote.invoice)
        .selectinload(Invoice.order)
        .selectinload(Order.payments),
    )


def fiscal_status(required: bool, eor: str | None) -> str:
    return "confirmed" if required and eor else "pending" if required else "not_required"


def invoice_paid_eur(invoice: Invoice) -> float:
    return (
        round(sum(payment.amount_eur for payment in invoice.order.payments), 2)
        if invoice.order
        else invoice.total_eur
    )


def serialize_credit_note(
    credit_note: CreditNote | None,
    invoice: Invoice | None = None,
) -> dict | None:
    if credit_note is None:
        return None
    invoice = invoice or credit_note.invoice
    paid_eur = invoice_paid_eur(invoice)
    refunded_eur = round(sum(refund.amount_eur for refund in credit_note.refunds), 2)
    refundable_eur = round(
        max(0.0, min(credit_note.total_eur, paid_eur) - refunded_eur), 2
    )
    return {
        "id": credit_note.id,
        "number": credit_note.number,
        "issued_on": credit_note.issued_on,
        "reason": credit_note.reason,
        "total_eur": credit_note.total_eur,
        "fiscal_status": fiscal_status(
            credit_note.fiscal_confirmation_required, credit_note.eor
        ),
        "eor": credit_note.eor,
        "zoi": credit_note.zoi,
        "pdf_sha256": credit_note.pdf_sha256,
        "paid_eur": paid_eur,
        "refunded_eur": refunded_eur,
        "refundable_eur": refundable_eur,
        "refunds": [
            {
                "id": refund.id,
                "refund_date": refund.refund_date,
                "amount_eur": refund.amount_eur,
                "payment_method": refund.payment_method,
                "notes": refund.notes,
            }
            for refund in sorted(
                credit_note.refunds,
                key=lambda item: (item.refund_date, item.id),
            )
        ],
    }


def serialize_invoice(invoice: Invoice) -> dict:
    paid_eur = invoice_paid_eur(invoice)
    return {
        "id": invoice.id,
        "number": invoice.number,
        "source_type": "order" if invoice.order_id else "retail_sale",
        "source_id": invoice.order_id or invoice.retail_sale_id,
        "issued_on": invoice.issued_on,
        "supply_date": invoice.supply_date,
        "due_date": invoice.due_date,
        "status": invoice.status,
        "payment_method": invoice.payment_method,
        "seller": {
            "name": invoice.seller_name,
            "address": invoice.seller_address,
            "tax_number": invoice.seller_tax_number,
            "iban": invoice.seller_iban,
            "registration_number": invoice.seller_registration_number,
        },
        "customer": {
            "name": invoice.customer_name,
            "address": invoice.customer_address,
            "tax_number": invoice.customer_tax_number,
        },
        "total_eur": invoice.total_eur,
        "paid_eur": paid_eur,
        "outstanding_eur": (
            0.0
            if invoice.status == "credited"
            else round(max(0.0, invoice.total_eur - paid_eur), 2)
        ),
        "fiscal_confirmation_required": invoice.fiscal_confirmation_required,
        "fiscal_status": fiscal_status(
            invoice.fiscal_confirmation_required, invoice.eor
        ),
        "eor": invoice.eor,
        "zoi": invoice.zoi,
        "vat_note": invoice.vat_note,
        "pdf_sha256": invoice.pdf_sha256,
        "lines": [
            {
                "description": line.description,
                "quantity": line.quantity,
                "unit": line.unit,
                "unit_price_eur": line.unit_price_eur,
                "line_total_eur": line.line_total_eur,
            }
            for line in invoice.lines
        ],
        "credit_note": serialize_credit_note(invoice.credit_note, invoice),
    }


def get_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.farm_id == DEFAULT_FARM_ID)
        .options(*invoice_load_options())
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Račun ne obstaja.")
    return invoice


@app.get("/api/invoices")
def list_invoices(db: Session = Depends(get_db)) -> list[dict]:
    invoices = db.scalars(
        select(Invoice)
        .where(Invoice.farm_id == DEFAULT_FARM_ID)
        .options(*invoice_load_options())
        .order_by(Invoice.issued_on.desc(), Invoice.id.desc())
    ).all()
    return [serialize_invoice(invoice) for invoice in invoices]


@app.get("/api/invoices/{invoice_id}")
def invoice_detail(invoice_id: int, db: Session = Depends(get_db)) -> dict:
    return serialize_invoice(get_invoice(db, invoice_id))


@app.post("/api/invoices", status_code=status.HTTP_201_CREATED)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)) -> dict:
    settings = get_sales_settings(db)
    profile = get_invoice_profile(db)
    if not settings.seller_name.strip() or not settings.seller_tax_number:
        raise HTTPException(
            status_code=422,
            detail="Pred izdajo računa v prodajnih nastavitvah vpišite naziv in davčno številko prodajalca.",
        )
    if not profile.seller_address:
        raise HTTPException(
            status_code=422,
            detail="Pred izdajo računa vpišite naslov prodajalca.",
        )

    if payload.source_type == "order":
        source = db.scalar(
            select(Order)
            .where(Order.id == payload.source_id, Order.farm_id == DEFAULT_FARM_ID)
            .options(*order_load_options())
        )
        if source is None:
            raise HTTPException(status_code=404, detail="Naročilo ne obstaja.")
        if source.invoice:
            raise HTTPException(status_code=409, detail="Za naročilo je račun že izdan.")
        if source.status != "fulfilled":
            raise HTTPException(status_code=409, detail="Račun je mogoče izdati po dostavi.")
        if not order_requires_invoice(source, settings):
            raise HTTPException(status_code=409, detail="Za to naročilo račun ni predviden.")
        customer = source.customer
        supply_date = source.delivery_date
        payment_method = payload.payment_method or "bank_transfer"
        source_fields = {"order_id": source.id, "retail_sale_id": None}
        source_items = source.items
    else:
        source = db.scalar(
            select(RetailSale)
            .where(
                RetailSale.id == payload.source_id,
                RetailSale.farm_id == DEFAULT_FARM_ID,
            )
            .options(*retail_sale_options())
        )
        if source is None:
            raise HTTPException(status_code=404, detail="Prodaja ne obstaja.")
        if source.invoice:
            raise HTTPException(status_code=409, detail="Za prodajo je račun že izdan.")
        if not retail_sale_requires_invoice(source, settings):
            raise HTTPException(status_code=409, detail="Za to prodajo račun ni predviden.")
        customer = source.customer
        supply_date = source.sale_date
        payment_method = payload.payment_method or source.payment_method
        source_fields = {"order_id": None, "retail_sale_id": source.id}
        source_items = source.items

    if customer is None or not customer.address:
        raise HTTPException(status_code=422, detail="Pred izdajo vpišite naslov kupca.")
    customer_tax_number = customer.profile.tax_number if customer.profile else None
    if not customer_tax_number:
        raise HTTPException(status_code=422, detail="Pred izdajo vpišite davčno številko kupca.")
    due_date = payload.due_date or payload.issued_on + timedelta(
        days=profile.default_due_days
    )
    if due_date < payload.issued_on:
        raise HTTPException(status_code=422, detail="Rok plačila ne sme biti pred datumom izdaje.")

    invoice = Invoice(
        farm_id=DEFAULT_FARM_ID,
        **source_fields,
        number=next_document_number(db, payload.issued_on, "invoice", profile),
        issued_on=payload.issued_on,
        supply_date=supply_date,
        due_date=due_date,
        status="issued",
        payment_method=payment_method,
        seller_name=settings.seller_name.strip(),
        seller_address=profile.seller_address,
        seller_tax_number=settings.seller_tax_number,
        seller_iban=profile.seller_iban,
        seller_registration_number=profile.seller_registration_number,
        vat_note=profile.vat_note,
        customer_name=customer.name,
        customer_address=customer.address,
        customer_tax_number=customer_tax_number,
        total_eur=source.total_eur,
        fiscal_confirmation_required=payment_method in {"cash", "card"},
    )
    invoice.lines = [
        InvoiceLine(
            description=(
                f"{item.harvest.planting.crop.name} – "
                f"{item.harvest.planting.variety.name}, kakovost {item.harvest.quality}"
            ),
            quantity=item.quantity_kg,
            unit="kg",
            unit_price_eur=item.price_per_kg_eur,
            line_total_eur=item.line_total_eur,
        )
        for item in source_items
    ]
    db.add(invoice)
    db.flush()
    if not invoice.fiscal_confirmation_required:
        invoice.pdf_data = build_invoice_pdf(invoice)
        invoice.pdf_sha256 = hashlib.sha256(invoice.pdf_data).hexdigest()
    db.commit()
    invoice = get_invoice(db, invoice.id)
    message = (
        "Račun je arhiviran. Pred končnim PDF vpišite EOR davčne potrditve."
        if invoice.fiscal_confirmation_required
        else "Račun je izdan in arhiviran."
    )
    return {"message": message, **serialize_invoice(invoice)}


@app.post("/api/invoices/{invoice_id}/fiscal-confirmation")
def confirm_invoice_fiscalization(
    invoice_id: int,
    payload: FiscalConfirmationCreate,
    db: Session = Depends(get_db),
) -> dict:
    invoice = get_invoice(db, invoice_id)
    if not invoice.fiscal_confirmation_required:
        raise HTTPException(status_code=409, detail="Ta račun ne potrebuje EOR.")
    if invoice.eor:
        raise HTTPException(status_code=409, detail="EOR je že arhiviran in ga ni mogoče zamenjati.")
    invoice.eor = payload.eor.strip()
    invoice.zoi = payload.zoi.strip() if payload.zoi else None
    db.flush()
    invoice.pdf_data = build_invoice_pdf(invoice)
    invoice.pdf_sha256 = hashlib.sha256(invoice.pdf_data).hexdigest()
    db.commit()
    return {"message": "EOR je nespremenljivo shranjen.", **serialize_invoice(invoice)}


@app.get("/api/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: int, db: Session = Depends(get_db)) -> Response:
    invoice = get_invoice(db, invoice_id)
    if invoice.fiscal_confirmation_required and not invoice.eor:
        raise HTTPException(
            status_code=409,
            detail="Končni PDF je na voljo po vpisu EOR davčne potrditve.",
        )
    if not invoice.pdf_data:
        raise HTTPException(status_code=409, detail="Arhivski PDF še ni ustvarjen.")
    return Response(
        content=invoice.pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{invoice.number}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


@app.post(
    "/api/invoices/{invoice_id}/credit-notes",
    status_code=status.HTTP_201_CREATED,
)
def create_credit_note(
    invoice_id: int,
    payload: CreditNoteCreate,
    db: Session = Depends(get_db),
) -> dict:
    invoice = get_invoice(db, invoice_id)
    if invoice.credit_note or invoice.status == "credited":
        raise HTTPException(status_code=409, detail="Račun že ima dobropis.")
    if payload.issued_on < invoice.issued_on:
        raise HTTPException(status_code=422, detail="Dobropis ne sme biti starejši od računa.")
    profile = get_invoice_profile(db)
    credit_note = CreditNote(
        farm_id=DEFAULT_FARM_ID,
        invoice_id=invoice.id,
        number=next_document_number(db, payload.issued_on, "credit_note", profile),
        issued_on=payload.issued_on,
        reason=payload.reason.strip(),
        total_eur=invoice.total_eur,
        fiscal_confirmation_required=invoice.fiscal_confirmation_required,
    )
    invoice.status = "credited"
    db.add(credit_note)
    db.flush()
    if not credit_note.fiscal_confirmation_required:
        credit_note.pdf_data = build_invoice_pdf(invoice, credit_note)
        credit_note.pdf_sha256 = hashlib.sha256(credit_note.pdf_data).hexdigest()
    db.commit()
    db.refresh(credit_note)
    message = (
        "Dobropis je arhiviran. Pred končnim PDF vpišite njegov EOR."
        if credit_note.fiscal_confirmation_required
        else "Dobropis je izdan; prvotni račun ostaja v arhivu."
    )
    return {"message": message, **serialize_credit_note(credit_note)}


@app.post("/api/credit-notes/{credit_note_id}/fiscal-confirmation")
def confirm_credit_note_fiscalization(
    credit_note_id: int,
    payload: FiscalConfirmationCreate,
    db: Session = Depends(get_db),
) -> dict:
    credit_note = db.scalar(
        select(CreditNote)
        .where(
            CreditNote.id == credit_note_id,
            CreditNote.farm_id == DEFAULT_FARM_ID,
        )
        .options(*credit_note_load_options())
    )
    if credit_note is None:
        raise HTTPException(status_code=404, detail="Dobropis ne obstaja.")
    if not credit_note.fiscal_confirmation_required:
        raise HTTPException(status_code=409, detail="Ta dobropis ne potrebuje EOR.")
    if credit_note.eor:
        raise HTTPException(status_code=409, detail="EOR dobropisa je že arhiviran.")
    credit_note.eor = payload.eor.strip()
    credit_note.zoi = payload.zoi.strip() if payload.zoi else None
    db.flush()
    credit_note.pdf_data = build_invoice_pdf(credit_note.invoice, credit_note)
    credit_note.pdf_sha256 = hashlib.sha256(credit_note.pdf_data).hexdigest()
    db.commit()
    return {
        "message": "EOR dobropisa je nespremenljivo shranjen.",
        **serialize_credit_note(credit_note),
    }


@app.get("/api/credit-notes/{credit_note_id}/pdf")
def credit_note_pdf(credit_note_id: int, db: Session = Depends(get_db)) -> Response:
    credit_note = db.scalar(
        select(CreditNote)
        .where(
            CreditNote.id == credit_note_id,
            CreditNote.farm_id == DEFAULT_FARM_ID,
        )
        .options(*credit_note_load_options())
    )
    if credit_note is None:
        raise HTTPException(status_code=404, detail="Dobropis ne obstaja.")
    if credit_note.fiscal_confirmation_required and not credit_note.eor:
        raise HTTPException(
            status_code=409,
            detail="Končni PDF dobropisa je na voljo po vpisu EOR.",
        )
    if not credit_note.pdf_data:
        raise HTTPException(status_code=409, detail="Arhivski PDF dobropisa še ni ustvarjen.")
    return Response(
        content=credit_note.pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{credit_note.number}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


@app.post(
    "/api/credit-notes/{credit_note_id}/refunds",
    status_code=status.HTTP_201_CREATED,
)
def record_refund(
    credit_note_id: int,
    payload: RefundCreate,
    db: Session = Depends(get_db),
) -> dict:
    credit_note = db.scalar(
        select(CreditNote)
        .where(
            CreditNote.id == credit_note_id,
            CreditNote.farm_id == DEFAULT_FARM_ID,
        )
        .options(*credit_note_load_options())
        .with_for_update()
    )
    if credit_note is None:
        raise HTTPException(status_code=404, detail="Dobropis ne obstaja.")
    ensure_business_day_open(db, payload.refund_date)
    if credit_note.fiscal_confirmation_required and not credit_note.eor:
        raise HTTPException(
            status_code=409,
            detail="Pred vračilom zaključite davčno potrditev dobropisa in vpišite EOR.",
        )
    if payload.refund_date < credit_note.issued_on:
        raise HTTPException(
            status_code=422,
            detail="Datum vračila ne sme biti pred datumom dobropisa.",
        )
    current = serialize_credit_note(credit_note, credit_note.invoice)
    refundable_eur = current["refundable_eur"]
    if refundable_eur <= 0:
        raise HTTPException(
            status_code=409,
            detail="Po tem dobropisu ni več mogoče evidentirati vračila.",
        )
    if payload.amount_eur > refundable_eur + 0.005:
        raise HTTPException(
            status_code=409,
            detail=f"Največji še vračljivi znesek je {refundable_eur:.2f} €.",
        )
    refund = Refund(
        farm_id=DEFAULT_FARM_ID,
        credit_note_id=credit_note.id,
        refund_date=payload.refund_date,
        amount_eur=round(payload.amount_eur, 2),
        payment_method=payload.payment_method,
        notes=payload.notes.strip() if payload.notes else None,
    )
    credit_note.refunds.append(refund)
    db.commit()
    return {
        "message": "Vračilo je evidentirano kot dejanski denarni odliv.",
        "refund": {
            "id": refund.id,
            "refund_date": refund.refund_date,
            "amount_eur": refund.amount_eur,
            "payment_method": refund.payment_method,
            "notes": refund.notes,
        },
        "credit_note": serialize_credit_note(credit_note, credit_note.invoice),
    }


def ensure_business_day_open(db: Session, business_date: date) -> None:
    closed = db.scalar(
        select(DayClose.id).where(
            DayClose.farm_id == DEFAULT_FARM_ID,
            DayClose.business_date == business_date,
        )
    )
    if closed is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Dan {business_date.isoformat()} je že zaključen. "
                "Novega denarnega vnosa za ta datum ni mogoče dodati."
            ),
        )


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
    ensure_business_day_open(db, payload.sale_date)
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
    if document_type == "invoice":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Sprotni račun je ukinjen. Izdajte nespremenljiv račun prek /api/invoices.",
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
        invoice_required = order_requires_invoice(order, settings)
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


def spreadsheet_cell(value: object) -> str:
    text = str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


@app.get("/api/sales-report/export.csv")
def export_sales_report(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> Response:
    report = build_sales_report(db, start, end)
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


PAYMENT_TERMS_DAYS = 14


def serialize_receivable(order: Order, as_of: date) -> dict:
    payments = sorted(
        (payment for payment in order.payments if payment.payment_date <= as_of),
        key=lambda item: (item.payment_date, item.id),
    )
    paid_eur = round(sum(payment.amount_eur for payment in payments), 2)
    due_date = (
        order.invoice.due_date
        if order.invoice
        else order.delivery_date + timedelta(days=PAYMENT_TERMS_DAYS)
    )
    outstanding_eur = (
        0.0
        if order.invoice and order.invoice.status == "credited"
        else round(max(0.0, order.total_eur - paid_eur), 2)
    )
    status_value = (
        "credited"
        if order.invoice and order.invoice.status == "credited"
        else "paid"
        if outstanding_eur <= 0
        else "overdue"
        if due_date < as_of
        else "partial"
        if paid_eur > 0
        else "open"
    )
    return {
        "order_id": order.id,
        "invoice_id": order.invoice.id if order.invoice else None,
        "invoice_number": (
            order.invoice.number
            if order.invoice
            else f"R-{order.order_date.year}-{order.id:04d}"
        ),
        "customer": order.customer.name,
        "customer_type": (
            order.customer.profile.customer_type if order.customer.profile else "consumer"
        ),
        "delivery_date": order.delivery_date,
        "due_date": due_date,
        "total_eur": order.total_eur,
        "paid_eur": paid_eur,
        "outstanding_eur": outstanding_eur,
        "status": status_value,
        "days_overdue": max(0, (as_of - due_date).days) if outstanding_eur > 0 else 0,
        "payments": [
            {
                "id": payment.id,
                "payment_date": payment.payment_date,
                "amount_eur": payment.amount_eur,
                "payment_method": payment.payment_method,
                "notes": payment.notes,
            }
            for payment in payments
        ],
    }


@app.get("/api/receivables")
def list_receivables(
    as_of: date | None = None,
    include_paid: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    target_date = as_of or date.today()
    settings = get_sales_settings(db)
    orders = db.scalars(
        select(Order)
        .where(
            Order.farm_id == DEFAULT_FARM_ID,
            Order.status == "fulfilled",
            Order.delivery_date <= target_date,
        )
        .options(*order_load_options())
    ).all()
    all_receivables = [
        serialize_receivable(order, target_date)
        for order in orders
        if order_requires_invoice(order, settings)
    ]
    receivables = all_receivables
    if not include_paid:
        receivables = [
            item for item in receivables if item["status"] not in {"paid", "credited"}
        ]
    receivables.sort(
        key=lambda item: (
            item["status"] == "paid",
            item["status"] != "overdue",
            item["due_date"],
            item["order_id"],
        )
    )
    return {
        "as_of": target_date,
        "payment_terms_days": PAYMENT_TERMS_DAYS,
        "summary": {
            "invoice_count": len(all_receivables),
            "open_count": sum(item["outstanding_eur"] > 0 for item in all_receivables),
            "overdue_count": sum(item["status"] == "overdue" for item in all_receivables),
            "invoiced_eur": round(sum(item["total_eur"] for item in all_receivables), 2),
            "paid_eur": round(sum(item["paid_eur"] for item in all_receivables), 2),
            "outstanding_eur": round(
                sum(item["outstanding_eur"] for item in all_receivables), 2
            ),
            "overdue_eur": round(
                sum(
                    item["outstanding_eur"]
                    for item in all_receivables
                    if item["status"] == "overdue"
                ),
                2,
            ),
        },
        "items": receivables,
        "note": (
            "Neposredne prodaje so poravnane ob prodaji. Terjatve vključujejo "
            "dostavljena naročila, za katera je potreben račun."
        ),
    }


@app.post("/api/orders/{order_id}/payments", status_code=status.HTTP_201_CREATED)
def record_order_payment(
    order_id: int,
    payload: OrderPaymentCreate,
    db: Session = Depends(get_db),
) -> dict:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.farm_id == DEFAULT_FARM_ID)
        .options(*order_load_options())
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Naročilo ne obstaja.")
    ensure_business_day_open(db, payload.payment_date)
    if order.status != "fulfilled":
        raise HTTPException(
            status_code=409,
            detail="Plačilo je mogoče evidentirati po dostavi naročila.",
        )
    settings = get_sales_settings(db)
    if not order_requires_invoice(order, settings):
        raise HTTPException(
            status_code=409,
            detail="Za to naročilo ni odprtega računa.",
        )
    if order.invoice and order.invoice.status == "credited":
        raise HTTPException(status_code=409, detail="Račun je dobropisan in nima odprte terjatve.")
    if payload.payment_date < order.order_date:
        raise HTTPException(
            status_code=422,
            detail="Datum plačila ne sme biti pred datumom naročila.",
        )
    outstanding_eur = serialize_order(order)["outstanding_eur"]
    if outstanding_eur <= 0:
        raise HTTPException(status_code=409, detail="Račun je že v celoti poravnan.")
    if payload.amount_eur > outstanding_eur + 0.005:
        raise HTTPException(
            status_code=409,
            detail=f"Odprti znesek je {outstanding_eur:.2f} €.",
        )
    db.add(
        OrderPayment(
            farm_id=DEFAULT_FARM_ID,
            order_id=order.id,
            payment_date=payload.payment_date,
            amount_eur=payload.amount_eur,
            payment_method=payload.payment_method,
            notes=payload.notes.strip() if payload.notes else None,
        )
    )
    db.commit()
    db.expire_all()
    order = db.scalar(
        select(Order).where(Order.id == order.id).options(*order_load_options())
    )
    receivable = serialize_receivable(order, payload.payment_date)
    message = (
        "Račun je v celoti poravnan."
        if receivable["status"] == "paid"
        else "Delno plačilo je evidentirano."
    )
    return {"message": message, **receivable}


def build_cash_flow(db: Session, start: date | None, end: date | None) -> dict:
    range_start, range_end = sales_report_range(start, end)
    retail_sales = db.scalars(
        select(RetailSale)
        .where(
            RetailSale.farm_id == DEFAULT_FARM_ID,
            RetailSale.sale_date >= range_start,
            RetailSale.sale_date <= range_end,
        )
        .options(
            selectinload(RetailSale.customer),
            selectinload(RetailSale.items),
        )
    ).all()
    order_payments = db.scalars(
        select(OrderPayment)
        .where(
            OrderPayment.farm_id == DEFAULT_FARM_ID,
            OrderPayment.payment_date >= range_start,
            OrderPayment.payment_date <= range_end,
        )
        .options(
            selectinload(OrderPayment.order).selectinload(Order.customer)
        )
    ).all()
    costs = db.scalars(
        select(Cost)
        .where(
            Cost.farm_id == DEFAULT_FARM_ID,
            Cost.cost_date >= range_start,
            Cost.cost_date <= range_end,
        )
        .options(selectinload(Cost.bed))
    ).all()
    refunds = db.scalars(
        select(Refund)
        .where(
            Refund.farm_id == DEFAULT_FARM_ID,
            Refund.refund_date >= range_start,
            Refund.refund_date <= range_end,
        )
        .options(
            selectinload(Refund.credit_note).selectinload(CreditNote.invoice)
        )
    ).all()
    supplier_payments = db.scalars(
        select(SupplierPayment)
        .where(
            SupplierPayment.farm_id == DEFAULT_FARM_ID,
            SupplierPayment.payment_date >= range_start,
            SupplierPayment.payment_date <= range_end,
        )
        .options(
            selectinload(SupplierPayment.purchase_order).selectinload(
                PurchaseOrder.supplier
            )
        )
    ).all()

    entries = []
    for retail_sale in retail_sales:
        entries.append(
            {
                "key": f"retail-{retail_sale.id}",
                "date": retail_sale.sale_date,
                "direction": "inflow",
                "source": "retail_sale",
                "reference": f"MP-{retail_sale.sale_date.year}-{retail_sale.id:04d}",
                "party": retail_sale.customer.name if retail_sale.customer else "Končni potrošnik",
                "description": "Hitra prodaja",
                "method": retail_sale.payment_method,
                "category": None,
                "amount_eur": retail_sale.total_eur,
            }
        )
    for payment in order_payments:
        entries.append(
            {
                "key": f"payment-{payment.id}",
                "date": payment.payment_date,
                "direction": "inflow",
                "source": "order_payment",
                "reference": f"R-{payment.order.order_date.year}-{payment.order.id:04d}",
                "party": payment.order.customer.name,
                "description": "Plačilo računa",
                "method": payment.payment_method,
                "category": None,
                "amount_eur": round(payment.amount_eur, 2),
            }
        )
    for cost in costs:
        entries.append(
            {
                "key": f"cost-{cost.id}",
                "date": cost.cost_date,
                "direction": "outflow",
                "source": "cost",
                "reference": f"ST-{cost.cost_date.year}-{cost.id:04d}",
                "party": f"Gredica {cost.bed.name}",
                "description": cost.description,
                "method": None,
                "category": cost.category,
                "amount_eur": round(cost.amount_eur, 2),
            }
        )
    for refund in refunds:
        entries.append(
            {
                "key": f"refund-{refund.id}",
                "date": refund.refund_date,
                "direction": "outflow",
                "source": "refund",
                "reference": refund.credit_note.number,
                "party": refund.credit_note.invoice.customer_name,
                "description": "Vračilo po dobropisu",
                "method": refund.payment_method,
                "category": None,
                "amount_eur": round(refund.amount_eur, 2),
            }
        )
    for payment in supplier_payments:
        entries.append(
            {
                "key": f"supplier-payment-{payment.id}",
                "date": payment.payment_date,
                "direction": "outflow",
                "source": "supplier_payment",
                "reference": (
                    f"NB-{payment.purchase_order.order_date.year}-"
                    f"{payment.purchase_order.id:04d}"
                ),
                "party": payment.purchase_order.supplier.name,
                "description": "Plačilo dobavitelju",
                "method": payment.payment_method,
                "category": "purchasing",
                "amount_eur": round(payment.amount_eur, 2),
            }
        )
    entries.sort(key=lambda entry: (entry["date"], entry["key"]), reverse=True)

    inflows = [entry for entry in entries if entry["direction"] == "inflow"]
    outflows = [entry for entry in entries if entry["direction"] == "outflow"]
    inflow_eur = round(sum(entry["amount_eur"] for entry in inflows), 2)
    outflow_eur = round(sum(entry["amount_eur"] for entry in outflows), 2)
    refund_entries = [entry for entry in entries if entry["source"] == "refund"]
    supplier_payment_entries = [
        entry for entry in entries if entry["source"] == "supplier_payment"
    ]
    methods = ("cash", "card", "bank_transfer")
    categories = sorted({entry["category"] for entry in outflows if entry["category"]})
    daily = []
    for report_date in sorted({entry["date"] for entry in entries}, reverse=True):
        day_entries = [entry for entry in entries if entry["date"] == report_date]
        day_inflow = round(
            sum(
                entry["amount_eur"]
                for entry in day_entries
                if entry["direction"] == "inflow"
            ),
            2,
        )
        day_outflow = round(
            sum(
                entry["amount_eur"]
                for entry in day_entries
                if entry["direction"] == "outflow"
            ),
            2,
        )
        daily.append(
            {
                "date": report_date,
                "inflow_eur": day_inflow,
                "outflow_eur": day_outflow,
                "net_eur": round(day_inflow - day_outflow, 2),
            }
        )
    return {
        "start": range_start,
        "end": range_end,
        "summary": {
            "inflow_eur": inflow_eur,
            "outflow_eur": outflow_eur,
            "net_eur": round(inflow_eur - outflow_eur, 2),
            "inflow_count": len(inflows),
            "outflow_count": len(outflows),
            "refund_eur": round(
                sum(entry["amount_eur"] for entry in refund_entries), 2
            ),
            "refund_count": len(refund_entries),
            "supplier_payments_eur": round(
                sum(entry["amount_eur"] for entry in supplier_payment_entries), 2
            ),
            "supplier_payment_count": len(supplier_payment_entries),
            **{
                f"{method}_eur": round(
                    sum(
                        entry["amount_eur"]
                        for entry in inflows
                        if entry["method"] == method
                    ),
                    2,
                )
                for method in methods
            },
            "costs_by_category": {
                category: round(
                    sum(
                        entry["amount_eur"]
                        for entry in outflows
                        if entry["category"] == category
                    ),
                    2,
                )
                for category in categories
            },
        },
        "daily": daily,
        "entries": entries,
        "note": (
            "Denarni tok vključuje poravnane hitre prodaje, dejansko evidentirana "
            "plačila računov, dejanska vračila po dobropisih, plačila dobaviteljem "
            "in neposredne stroške. Vračilo "
            "je odliv na datum vračila, vendar ni poslovni strošek gredice. "
            "Izdani računi brez plačila ter stare ročne prodaje brez načina plačila "
            "niso vključeni."
        ),
    }


@app.get("/api/cash-flow")
def cash_flow(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> dict:
    return build_cash_flow(db, start, end)


@app.get("/api/cash-flow/export.csv")
def export_cash_flow(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> Response:
    report = build_cash_flow(db, start, end)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "Datum",
            "Smer",
            "Vir",
            "Referenca",
            "Stranka ali gredica",
            "Opis",
            "Način",
            "Kategorija",
            "Znesek EUR",
        ]
    )
    for entry in report["entries"]:
        writer.writerow(
            [
                entry["date"].isoformat(),
                entry["direction"],
                entry["source"],
                spreadsheet_cell(entry["reference"]),
                spreadsheet_cell(entry["party"]),
                spreadsheet_cell(entry["description"]),
                spreadsheet_cell(entry["method"] or ""),
                spreadsheet_cell(entry["category"] or ""),
                f'{entry["amount_eur"]:.2f}',
            ]
        )
    filename = f'growmaster-denarni-tok-{report["start"]}-{report["end"]}.csv'
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def build_day_close_preview(
    db: Session,
    business_date: date,
    opening_cash_eur: float,
) -> dict:
    retail_sales = db.scalars(
        select(RetailSale)
        .where(
            RetailSale.farm_id == DEFAULT_FARM_ID,
            RetailSale.sale_date == business_date,
        )
        .options(selectinload(RetailSale.items))
    ).all()
    payments = db.scalars(
        select(OrderPayment).where(
            OrderPayment.farm_id == DEFAULT_FARM_ID,
            OrderPayment.payment_date == business_date,
        )
    ).all()
    refunds = db.scalars(
        select(Refund).where(
            Refund.farm_id == DEFAULT_FARM_ID,
            Refund.refund_date == business_date,
        )
    ).all()
    supplier_payments = db.scalars(
        select(SupplierPayment).where(
            SupplierPayment.farm_id == DEFAULT_FARM_ID,
            SupplierPayment.payment_date == business_date,
        )
    ).all()
    methods = ("cash", "card", "bank_transfer")
    inflow_by_method = {
        method: round(
            sum(
                sale.total_eur
                for sale in retail_sales
                if sale.payment_method == method
            )
            + sum(
                payment.amount_eur
                for payment in payments
                if payment.payment_method == method
            ),
            2,
        )
        for method in methods
    }
    refund_by_method = {
        method: round(
            sum(
                refund.amount_eur
                for refund in refunds
                if refund.payment_method == method
            ),
            2,
        )
        for method in methods
    }
    supplier_out_by_method = {
        method: round(
            sum(
                payment.amount_eur
                for payment in supplier_payments
                if payment.payment_method == method
            ),
            2,
        )
        for method in methods
    }
    total_inflow_eur = round(sum(inflow_by_method.values()), 2)
    total_refund_eur = round(sum(refund_by_method.values()), 2)
    total_supplier_payment_eur = round(sum(supplier_out_by_method.values()), 2)
    opening_cash_eur = round(opening_cash_eur, 2)
    return {
        "business_date": business_date,
        "opening_cash_eur": opening_cash_eur,
        "cash_in_eur": inflow_by_method["cash"],
        "cash_refund_eur": refund_by_method["cash"],
        "card_in_eur": inflow_by_method["card"],
        "card_refund_eur": refund_by_method["card"],
        "bank_transfer_in_eur": inflow_by_method["bank_transfer"],
        "bank_transfer_refund_eur": refund_by_method["bank_transfer"],
        "cash_supplier_payment_eur": supplier_out_by_method["cash"],
        "card_supplier_payment_eur": supplier_out_by_method["card"],
        "bank_transfer_supplier_payment_eur": supplier_out_by_method[
            "bank_transfer"
        ],
        "total_inflow_eur": total_inflow_eur,
        "total_refund_eur": total_refund_eur,
        "total_supplier_payment_eur": total_supplier_payment_eur,
        "total_outflow_eur": round(
            total_refund_eur + total_supplier_payment_eur, 2
        ),
        "net_receipts_eur": round(
            total_inflow_eur - total_refund_eur - total_supplier_payment_eur,
            2,
        ),
        "expected_cash_eur": round(
            opening_cash_eur
            + inflow_by_method["cash"]
            - refund_by_method["cash"]
            - supplier_out_by_method["cash"],
            2,
        ),
        "retail_sale_count": len(retail_sales),
        "payment_count": len(payments),
        "refund_count": len(refunds),
        "supplier_payment_count": len(supplier_payments),
    }


def serialize_day_close(day_close: DayClose) -> dict:
    snapshot = day_close.supplier_payment_snapshot
    cash_supplier_payment_eur = snapshot.cash_out_eur if snapshot else 0
    card_supplier_payment_eur = snapshot.card_out_eur if snapshot else 0
    bank_supplier_payment_eur = snapshot.bank_transfer_out_eur if snapshot else 0
    total_supplier_payment_eur = round(
        cash_supplier_payment_eur
        + card_supplier_payment_eur
        + bank_supplier_payment_eur,
        2,
    )
    return {
        "id": day_close.id,
        "business_date": day_close.business_date,
        "opening_cash_eur": day_close.opening_cash_eur,
        "cash_in_eur": day_close.cash_in_eur,
        "cash_refund_eur": day_close.cash_refund_eur,
        "card_in_eur": day_close.card_in_eur,
        "card_refund_eur": day_close.card_refund_eur,
        "bank_transfer_in_eur": day_close.bank_transfer_in_eur,
        "bank_transfer_refund_eur": day_close.bank_transfer_refund_eur,
        "cash_supplier_payment_eur": cash_supplier_payment_eur,
        "card_supplier_payment_eur": card_supplier_payment_eur,
        "bank_transfer_supplier_payment_eur": bank_supplier_payment_eur,
        "total_inflow_eur": day_close.total_inflow_eur,
        "total_refund_eur": day_close.total_refund_eur,
        "total_supplier_payment_eur": total_supplier_payment_eur,
        "total_outflow_eur": round(
            day_close.total_refund_eur + total_supplier_payment_eur, 2
        ),
        "net_receipts_eur": round(
            day_close.total_inflow_eur
            - day_close.total_refund_eur
            - total_supplier_payment_eur,
            2,
        ),
        "expected_cash_eur": day_close.expected_cash_eur,
        "counted_cash_eur": day_close.counted_cash_eur,
        "difference_eur": day_close.difference_eur,
        "retail_sale_count": day_close.retail_sale_count,
        "payment_count": day_close.payment_count,
        "refund_count": day_close.refund_count,
        "supplier_payment_count": snapshot.payment_count if snapshot else 0,
        "notes": day_close.notes,
        "closed_at": day_close.closed_at,
    }


@app.get("/api/day-closes")
def list_day_closes(db: Session = Depends(get_db)) -> list[dict]:
    closes = db.scalars(
        select(DayClose)
        .where(DayClose.farm_id == DEFAULT_FARM_ID)
        .options(selectinload(DayClose.supplier_payment_snapshot))
        .order_by(DayClose.business_date.desc(), DayClose.id.desc())
    ).all()
    return [serialize_day_close(day_close) for day_close in closes]


@app.get("/api/day-closes/preview")
def day_close_preview(
    business_date: date,
    opening_cash_eur: float = Query(default=0, ge=0, le=1000000),
    db: Session = Depends(get_db),
) -> dict:
    existing = db.scalar(
        select(DayClose)
        .where(
            DayClose.farm_id == DEFAULT_FARM_ID,
            DayClose.business_date == business_date,
        )
        .options(selectinload(DayClose.supplier_payment_snapshot))
    )
    if existing:
        return {"closed": True, **serialize_day_close(existing)}
    return {
        "closed": False,
        **build_day_close_preview(db, business_date, opening_cash_eur),
    }


@app.post("/api/day-closes", status_code=status.HTTP_201_CREATED)
def close_business_day(
    payload: DayCloseCreate,
    db: Session = Depends(get_db),
) -> dict:
    existing = db.scalar(
        select(DayClose)
        .where(
            DayClose.farm_id == DEFAULT_FARM_ID,
            DayClose.business_date == payload.business_date,
        )
        .with_for_update()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ta poslovni dan je že zaključen.")
    preview = build_day_close_preview(
        db, payload.business_date, payload.opening_cash_eur
    )
    day_close = DayClose(
        farm_id=DEFAULT_FARM_ID,
        business_date=payload.business_date,
        opening_cash_eur=preview["opening_cash_eur"],
        cash_in_eur=preview["cash_in_eur"],
        cash_refund_eur=preview["cash_refund_eur"],
        card_in_eur=preview["card_in_eur"],
        card_refund_eur=preview["card_refund_eur"],
        bank_transfer_in_eur=preview["bank_transfer_in_eur"],
        bank_transfer_refund_eur=preview["bank_transfer_refund_eur"],
        total_inflow_eur=preview["total_inflow_eur"],
        total_refund_eur=preview["total_refund_eur"],
        expected_cash_eur=preview["expected_cash_eur"],
        counted_cash_eur=round(payload.counted_cash_eur, 2),
        difference_eur=round(
            payload.counted_cash_eur - preview["expected_cash_eur"], 2
        ),
        retail_sale_count=preview["retail_sale_count"],
        payment_count=preview["payment_count"],
        refund_count=preview["refund_count"],
        notes=payload.notes.strip() if payload.notes else None,
        supplier_payment_snapshot=DayCloseSupplierPaymentSnapshot(
            cash_out_eur=preview["cash_supplier_payment_eur"],
            card_out_eur=preview["card_supplier_payment_eur"],
            bank_transfer_out_eur=preview[
                "bank_transfer_supplier_payment_eur"
            ],
            payment_count=preview["supplier_payment_count"],
        ),
    )
    db.add(day_close)
    db.commit()
    db.refresh(day_close)
    return {
        "message": "Poslovni dan je zaključen in denarni vnosi za ta datum so zaklenjeni.",
        **serialize_day_close(day_close),
    }


def serialize_supplier(supplier: Supplier) -> dict:
    return {
        "id": supplier.id,
        "name": supplier.name,
        "tax_number": supplier.tax_number,
        "email": supplier.email,
        "phone": supplier.phone,
        "notes": supplier.notes,
    }


def serialize_supply_item(supply_item: SupplyItem) -> dict:
    return {
        "id": supply_item.id,
        "name": supply_item.name,
        "category": supply_item.category,
        "unit": supply_item.unit,
        "stock_quantity": round(supply_item.stock_quantity, 3),
        "reorder_level": round(supply_item.reorder_level, 3),
        "low_stock": (
            supply_item.reorder_level > 0
            and supply_item.stock_quantity <= supply_item.reorder_level
        ),
    }


def purchase_order_load_options() -> tuple:
    return (
        selectinload(PurchaseOrder.supplier),
        selectinload(PurchaseOrder.items).selectinload(
            PurchaseOrderItem.supply_item
        ),
        selectinload(PurchaseOrder.payments),
    )


def serialize_purchase_order(purchase_order: PurchaseOrder) -> dict:
    paid_eur = round(sum(payment.amount_eur for payment in purchase_order.payments), 2)
    outstanding_eur = round(max(purchase_order.total_eur - paid_eur, 0), 2)
    payment_status = (
        "paid" if outstanding_eur <= 0 else "partial" if paid_eur > 0 else "unpaid"
    )
    return {
        "id": purchase_order.id,
        "number": f"NB-{purchase_order.order_date.year}-{purchase_order.id:04d}",
        "supplier": serialize_supplier(purchase_order.supplier),
        "order_date": purchase_order.order_date,
        "expected_date": purchase_order.expected_date,
        "received_on": purchase_order.received_on,
        "status": purchase_order.status,
        "payment_method": purchase_order.payment_method,
        "notes": purchase_order.notes,
        "total_eur": purchase_order.total_eur,
        "paid_eur": paid_eur,
        "outstanding_eur": outstanding_eur,
        "payment_status": payment_status,
        "payments": [
            {
                "id": payment.id,
                "payment_date": payment.payment_date,
                "amount_eur": payment.amount_eur,
                "payment_method": payment.payment_method,
                "notes": payment.notes,
            }
            for payment in sorted(
                purchase_order.payments,
                key=lambda item: (item.payment_date, item.id),
            )
        ],
        "items": [
            {
                "id": item.id,
                "supply_item_id": item.supply_item_id,
                "name": item.supply_item.name,
                "category": item.supply_item.category,
                "unit": item.supply_item.unit,
                "quantity": item.quantity,
                "unit_price_eur": item.unit_price_eur,
                "line_total_eur": item.line_total_eur,
            }
            for item in purchase_order.items
        ],
    }


@app.get("/api/suppliers")
def list_suppliers(db: Session = Depends(get_db)) -> list[dict]:
    suppliers = db.scalars(
        select(Supplier)
        .where(Supplier.farm_id == DEFAULT_FARM_ID)
        .order_by(Supplier.name, Supplier.id)
    ).all()
    return [serialize_supplier(supplier) for supplier in suppliers]


@app.post("/api/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)) -> dict:
    name = payload.name.strip()
    existing = db.scalar(
        select(Supplier.id).where(
            Supplier.farm_id == DEFAULT_FARM_ID,
            func.lower(Supplier.name) == name.lower(),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Dobavitelj s tem nazivom že obstaja.")
    supplier = Supplier(
        farm_id=DEFAULT_FARM_ID,
        name=name,
        tax_number=payload.tax_number.strip() if payload.tax_number else None,
        email=payload.email.strip() if payload.email else None,
        phone=payload.phone.strip() if payload.phone else None,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return {"message": "Dobavitelj je dodan.", **serialize_supplier(supplier)}


@app.get("/api/supply-items")
def list_supply_items(db: Session = Depends(get_db)) -> list[dict]:
    supply_items = db.scalars(
        select(SupplyItem)
        .where(SupplyItem.farm_id == DEFAULT_FARM_ID)
        .order_by(SupplyItem.category, SupplyItem.name, SupplyItem.id)
    ).all()
    return [serialize_supply_item(supply_item) for supply_item in supply_items]


@app.post("/api/supply-items", status_code=status.HTTP_201_CREATED)
def create_supply_item(
    payload: SupplyItemCreate,
    db: Session = Depends(get_db),
) -> dict:
    name = payload.name.strip()
    existing = db.scalar(
        select(SupplyItem.id).where(
            SupplyItem.farm_id == DEFAULT_FARM_ID,
            func.lower(SupplyItem.name) == name.lower(),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Material s tem nazivom že obstaja.")
    supply_item = SupplyItem(
        farm_id=DEFAULT_FARM_ID,
        name=name,
        category=payload.category,
        unit=payload.unit.strip(),
        stock_quantity=round(payload.opening_stock, 3),
        reorder_level=round(payload.reorder_level, 3),
    )
    db.add(supply_item)
    db.commit()
    db.refresh(supply_item)
    return {"message": "Material je dodan v katalog.", **serialize_supply_item(supply_item)}


@app.get("/api/purchase-orders")
def list_purchase_orders(db: Session = Depends(get_db)) -> list[dict]:
    purchase_orders = db.scalars(
        select(PurchaseOrder)
        .where(PurchaseOrder.farm_id == DEFAULT_FARM_ID)
        .options(*purchase_order_load_options())
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
    ).all()
    return [
        serialize_purchase_order(purchase_order)
        for purchase_order in purchase_orders
    ]


@app.post("/api/purchase-orders", status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
) -> dict:
    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == payload.supplier_id,
            Supplier.farm_id == DEFAULT_FARM_ID,
        )
    )
    if supplier is None:
        raise HTTPException(status_code=404, detail="Dobavitelj ne obstaja.")
    if payload.expected_date and payload.expected_date < payload.order_date:
        raise HTTPException(
            status_code=422,
            detail="Predvideni prevzem ne sme biti pred datumom naročila.",
        )
    supply_item_ids = [item.supply_item_id for item in payload.items]
    if len(supply_item_ids) != len(set(supply_item_ids)):
        raise HTTPException(
            status_code=422,
            detail="Isti material je lahko v naročilu samo enkrat.",
        )
    supply_items = db.scalars(
        select(SupplyItem).where(
            SupplyItem.farm_id == DEFAULT_FARM_ID,
            SupplyItem.id.in_(supply_item_ids),
        )
    ).all()
    supply_items_by_id = {item.id: item for item in supply_items}
    missing = [item_id for item_id in supply_item_ids if item_id not in supply_items_by_id]
    if missing:
        raise HTTPException(status_code=404, detail="Izbrani material ne obstaja.")
    purchase_order = PurchaseOrder(
        farm_id=DEFAULT_FARM_ID,
        supplier_id=supplier.id,
        order_date=payload.order_date,
        expected_date=payload.expected_date,
        status="ordered",
        payment_method=payload.payment_method,
        notes=payload.notes.strip() if payload.notes else None,
        items=[
            PurchaseOrderItem(
                supply_item_id=item.supply_item_id,
                quantity=round(item.quantity, 3),
                unit_price_eur=round(item.unit_price_eur, 4),
            )
            for item in payload.items
        ],
    )
    db.add(purchase_order)
    db.commit()
    purchase_order = db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == purchase_order.id)
        .options(*purchase_order_load_options())
    )
    return {
        "message": "Nabavno naročilo je ustvarjeno.",
        **serialize_purchase_order(purchase_order),
    }


@app.post("/api/purchase-orders/{purchase_order_id}/receive")
def receive_purchase_order(
    purchase_order_id: int,
    payload: PurchaseOrderReceive,
    db: Session = Depends(get_db),
) -> dict:
    purchase_order = db.scalar(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.farm_id == DEFAULT_FARM_ID,
        )
        .options(*purchase_order_load_options())
        .with_for_update()
    )
    if purchase_order is None:
        raise HTTPException(status_code=404, detail="Nabavno naročilo ne obstaja.")
    if purchase_order.status != "ordered":
        raise HTTPException(
            status_code=409,
            detail="Prevzeti je mogoče samo odprto nabavno naročilo.",
        )
    if payload.received_on < purchase_order.order_date:
        raise HTTPException(
            status_code=422,
            detail="Datum prevzema ne sme biti pred datumom naročila.",
        )
    for item in purchase_order.items:
        item.supply_item.stock_quantity = round(
            item.supply_item.stock_quantity + item.quantity, 3
        )
    purchase_order.status = "received"
    purchase_order.received_on = payload.received_on
    db.commit()
    return {
        "message": "Naročilo je prevzeto, zaloga materiala pa posodobljena.",
        **serialize_purchase_order(purchase_order),
    }


@app.post("/api/purchase-orders/{purchase_order_id}/cancel")
def cancel_purchase_order(
    purchase_order_id: int,
    db: Session = Depends(get_db),
) -> dict:
    purchase_order = db.scalar(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.farm_id == DEFAULT_FARM_ID,
        )
        .options(*purchase_order_load_options())
        .with_for_update()
    )
    if purchase_order is None:
        raise HTTPException(status_code=404, detail="Nabavno naročilo ne obstaja.")
    if purchase_order.status != "ordered":
        raise HTTPException(
            status_code=409,
            detail="Preklicati je mogoče samo odprto nabavno naročilo.",
        )
    if purchase_order.payments:
        raise HTTPException(
            status_code=409,
            detail="Naročila z evidentiranim plačilom ni mogoče preklicati.",
        )
    purchase_order.status = "cancelled"
    db.commit()
    return {
        "message": "Nabavno naročilo je preklicano.",
        **serialize_purchase_order(purchase_order),
    }


def serialize_supply_usage(usage: SupplyUsage) -> dict:
    return {
        "id": usage.id,
        "usage_date": usage.usage_date,
        "supply_item_id": usage.supply_item_id,
        "supply_item": usage.supply_item.name,
        "category": usage.supply_item.category,
        "unit": usage.supply_item.unit,
        "bed_id": usage.bed_id,
        "bed": usage.bed.name,
        "planting_id": usage.planting_id,
        "quantity": usage.quantity,
        "unit_cost_eur": usage.unit_cost_eur,
        "total_cost_eur": usage.total_cost_eur,
        "notes": usage.notes,
    }


def average_received_unit_cost(db: Session, supply_item_id: int) -> float | None:
    received_items = db.scalars(
        select(PurchaseOrderItem)
        .join(
            PurchaseOrder,
            PurchaseOrderItem.purchase_order_id == PurchaseOrder.id,
        )
        .where(
            PurchaseOrder.farm_id == DEFAULT_FARM_ID,
            PurchaseOrder.status == "received",
            PurchaseOrderItem.supply_item_id == supply_item_id,
        )
    ).all()
    received_quantity = sum(item.quantity for item in received_items)
    if received_quantity <= 0:
        return None
    return round(
        sum(item.quantity * item.unit_price_eur for item in received_items)
        / received_quantity,
        4,
    )


@app.get("/api/supply-usages")
def list_supply_usages(db: Session = Depends(get_db)) -> list[dict]:
    usages = db.scalars(
        select(SupplyUsage)
        .where(SupplyUsage.farm_id == DEFAULT_FARM_ID)
        .options(
            selectinload(SupplyUsage.supply_item),
            selectinload(SupplyUsage.bed),
        )
        .order_by(SupplyUsage.usage_date.desc(), SupplyUsage.id.desc())
    ).all()
    return [serialize_supply_usage(usage) for usage in usages]


@app.post("/api/supply-usages", status_code=status.HTTP_201_CREATED)
def create_supply_usage(
    payload: SupplyUsageCreate,
    db: Session = Depends(get_db),
) -> dict:
    supply_item = db.scalar(
        select(SupplyItem)
        .where(
            SupplyItem.id == payload.supply_item_id,
            SupplyItem.farm_id == DEFAULT_FARM_ID,
        )
        .with_for_update()
    )
    if supply_item is None:
        raise HTTPException(status_code=404, detail="Material ne obstaja.")
    bed = db.scalar(
        select(Bed).where(
            Bed.id == payload.bed_id,
            Bed.farm_id == DEFAULT_FARM_ID,
        )
    )
    if bed is None:
        raise HTTPException(status_code=404, detail="Gredica ne obstaja.")
    if payload.planting_id is not None:
        planting = db.scalar(
            select(Planting).where(
                Planting.id == payload.planting_id,
                Planting.farm_id == DEFAULT_FARM_ID,
            )
        )
        if planting is None:
            raise HTTPException(status_code=404, detail="Setev ne obstaja.")
        if planting.bed_id != bed.id:
            raise HTTPException(
                status_code=422,
                detail="Setev ne pripada izbrani gredici.",
            )
    if payload.quantity > supply_item.stock_quantity + 0.0005:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Na zalogi je samo {supply_item.stock_quantity:.3f} "
                f"{supply_item.unit}."
            ),
        )
    unit_cost_eur = payload.unit_cost_eur or average_received_unit_cost(
        db, supply_item.id
    )
    if unit_cost_eur is None:
        raise HTTPException(
            status_code=422,
            detail="Za material brez prevzete nabave vnesite strošek na enoto.",
        )
    usage = SupplyUsage(
        farm_id=DEFAULT_FARM_ID,
        supply_item_id=supply_item.id,
        bed_id=bed.id,
        planting_id=payload.planting_id,
        usage_date=payload.usage_date,
        quantity=round(payload.quantity, 3),
        unit_cost_eur=round(unit_cost_eur, 4),
        notes=payload.notes.strip() if payload.notes else None,
    )
    supply_item.stock_quantity = round(
        supply_item.stock_quantity - payload.quantity, 3
    )
    db.add(usage)
    db.commit()
    usage = db.scalar(
        select(SupplyUsage)
        .where(SupplyUsage.id == usage.id)
        .options(
            selectinload(SupplyUsage.supply_item),
            selectinload(SupplyUsage.bed),
        )
    )
    return {
        "message": "Poraba materiala je knjižena na gredico in odšteta iz zaloge.",
        **serialize_supply_usage(usage),
    }


@app.post(
    "/api/purchase-orders/{purchase_order_id}/payments",
    status_code=status.HTTP_201_CREATED,
)
def record_supplier_payment(
    purchase_order_id: int,
    payload: SupplierPaymentCreate,
    db: Session = Depends(get_db),
) -> dict:
    purchase_order = db.scalar(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.farm_id == DEFAULT_FARM_ID,
        )
        .options(*purchase_order_load_options())
        .with_for_update()
    )
    if purchase_order is None:
        raise HTTPException(status_code=404, detail="Nabavno naročilo ne obstaja.")
    ensure_business_day_open(db, payload.payment_date)
    if purchase_order.status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="Plačila preklicanega naročila ni mogoče evidentirati.",
        )
    if payload.payment_date < purchase_order.order_date:
        raise HTTPException(
            status_code=422,
            detail="Datum plačila ne sme biti pred datumom naročila.",
        )
    current = serialize_purchase_order(purchase_order)
    outstanding_eur = current["outstanding_eur"]
    if outstanding_eur <= 0:
        raise HTTPException(status_code=409, detail="Naročilo je že v celoti plačano.")
    if payload.amount_eur > outstanding_eur + 0.005:
        raise HTTPException(
            status_code=409,
            detail=f"Največji še plačljivi znesek je {outstanding_eur:.2f} €.",
        )
    purchase_order.payments.append(
        SupplierPayment(
            farm_id=DEFAULT_FARM_ID,
            payment_date=payload.payment_date,
            amount_eur=round(payload.amount_eur, 2),
            payment_method=payload.payment_method,
            notes=payload.notes.strip() if payload.notes else None,
        )
    )
    db.commit()
    purchase_order = db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == purchase_order.id)
        .options(*purchase_order_load_options())
    )
    data = serialize_purchase_order(purchase_order)
    message = (
        "Nabavno naročilo je v celoti plačano."
        if data["payment_status"] == "paid"
        else "Delno plačilo dobavitelju je evidentirano."
    )
    return {"message": message, **data}
