from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import PurchaseOrder, PurchaseOrderItem, Supplier, SupplyItem
from app.seed_inventory_service import create_lot

router = APIRouter()
DEFAULT_FARM_ID = 1


class SeedPurchaseCreate(BaseModel):
    supplier_id: int
    crop: str = Field(min_length=1, max_length=120)
    variety: str | None = Field(default=None, max_length=120)
    quantity: float = Field(gt=0, le=1_000_000)
    unit: str = Field(pattern="^(g|seeds|pellets)$")
    unit_price_eur: float = Field(gt=0, le=1_000_000)
    order_date: date = Field(default_factory=date.today)
    expected_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class SeedPurchaseFromOffer(BaseModel):
    supplier_name: str = Field(min_length=1, max_length=160)
    crop: str = Field(min_length=1, max_length=120)
    variety: str | None = Field(default=None, max_length=120)
    quantity: float = Field(gt=0, le=1_000_000)
    unit: str = Field(pattern="^(g|seeds|pellets)$")
    total_price_eur: float = Field(gt=0, le=1_000_000)
    source_url: str = Field(min_length=8, max_length=1000)
    offer_title: str | None = Field(default=None, max_length=300)
    order_date: date = Field(default_factory=date.today)
    expected_date: date | None = None


class SeedPurchaseReceive(BaseModel):
    received_on: date = Field(default_factory=date.today)
    received_quantity: float | None = Field(default=None, gt=0, le=1_000_000)
    lot_number: str | None = Field(default=None, max_length=120)
    package_size: float | None = Field(default=None, gt=0)
    thousand_seed_weight_g: float | None = Field(default=None, gt=0)
    germination_pct: float = Field(default=95, gt=0, le=100)
    field_emergence_pct: float = Field(default=90, gt=0, le=100)
    expiry_date: str | None = None


def _load_order(db: Session, order_id: int) -> PurchaseOrder | None:
    return db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == order_id, PurchaseOrder.farm_id == DEFAULT_FARM_ID)
        .options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.supply_item),
        )
    )


def _seed_marker(order: PurchaseOrder) -> tuple[str, str, str] | None:
    marker = next(
        (
            line
            for line in (order.notes or "").splitlines()
            if line.startswith("[seed:") and line.endswith("]")
        ),
        None,
    )
    if marker is None:
        return None
    parts = marker[6:-1].split("|", 2)
    return tuple(parts) if len(parts) == 3 else None


def _seed_offer_url(order: PurchaseOrder) -> str | None:
    for line in (order.notes or "").splitlines():
        if line.startswith("[seed-offer-url:") and line.endswith("]"):
            return line[len("[seed-offer-url:") : -1]
    return None


def _ensure_supply_item(db: Session, crop: str, variety: str | None, unit: str) -> SupplyItem:
    item_name = f"Seme – {crop} {variety or ''}".strip()
    supply_item = db.scalar(
        select(SupplyItem).where(
            SupplyItem.farm_id == DEFAULT_FARM_ID,
            SupplyItem.name == item_name,
        )
    )
    if supply_item is None:
        supply_item = SupplyItem(
            farm_id=DEFAULT_FARM_ID,
            name=item_name,
            category="seed",
            unit=unit,
            stock_quantity=0,
            reorder_level=0,
        )
        db.add(supply_item)
        db.flush()
    elif supply_item.unit != unit:
        raise HTTPException(
            status_code=409,
            detail=f"Material {item_name} že uporablja enoto {supply_item.unit}; naročilo uporablja {unit}.",
        )
    return supply_item


def _create_order(
    db: Session,
    *,
    supplier: Supplier,
    crop: str,
    variety: str | None,
    quantity: float,
    unit: str,
    unit_price_eur: float,
    order_date: date,
    expected_date: date | None,
    notes: str | None,
) -> PurchaseOrder:
    supply_item = _ensure_supply_item(db, crop, variety, unit)
    order = PurchaseOrder(
        farm_id=DEFAULT_FARM_ID,
        supplier_id=supplier.id,
        order_date=order_date,
        expected_date=expected_date,
        received_on=None,
        status="ordered",
        payment_method="bank_transfer",
        notes=(notes or "") + f"\n[seed:{crop}|{variety or ''}|{unit}]",
    )
    db.add(order)
    db.flush()
    order.items.append(
        PurchaseOrderItem(
            supply_item_id=supply_item.id,
            quantity=quantity,
            unit_price_eur=unit_price_eur,
        )
    )
    db.commit()
    db.refresh(order)
    return order


@router.post("/api/seed-inventory/purchase-orders", status_code=status.HTTP_201_CREATED)
def create_seed_purchase_order(body: SeedPurchaseCreate, db: Session = Depends(get_db)) -> dict:
    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == body.supplier_id,
            Supplier.farm_id == DEFAULT_FARM_ID,
        )
    )
    if supplier is None:
        raise HTTPException(status_code=404, detail="Dobavitelj ne obstaja.")
    order = _create_order(
        db,
        supplier=supplier,
        crop=body.crop,
        variety=body.variety,
        quantity=body.quantity,
        unit=body.unit,
        unit_price_eur=body.unit_price_eur,
        order_date=body.order_date,
        expected_date=body.expected_date,
        notes=body.notes,
    )
    return {
        "message": "Semensko naročilo je ustvarjeno v GrowMaster Nabavi. Zaloga se še ni povečala.",
        "purchase_order_id": order.id,
        "supplier": supplier.name,
        "crop": body.crop,
        "variety": body.variety,
        "quantity": body.quantity,
        "unit": body.unit,
        "total_eur": round(body.quantity * body.unit_price_eur, 2),
        "status": order.status,
        "inventory_changed": False,
    }


@router.post("/api/seed-inventory/purchase-orders/from-offer", status_code=status.HTTP_201_CREATED)
def create_seed_purchase_from_offer(body: SeedPurchaseFromOffer, db: Session = Depends(get_db)) -> dict:
    if not body.source_url.startswith(("https://", "http://")):
        raise HTTPException(status_code=422, detail="Povezava ponudbe ni veljavna.")
    supplier = db.scalar(
        select(Supplier).where(
            Supplier.farm_id == DEFAULT_FARM_ID,
            Supplier.name == body.supplier_name,
        )
    )
    if supplier is None:
        supplier = Supplier(
            farm_id=DEFAULT_FARM_ID,
            name=body.supplier_name,
            notes="Samodejno ustvarjen iz GrowMaster spletnega iskalnika semen.",
        )
        db.add(supplier)
        db.flush()
    unit_price = body.total_price_eur / body.quantity
    notes = "\n".join(
        item
        for item in (
            f"Spletna ponudba: {body.offer_title}" if body.offer_title else None,
            f"[seed-offer-url:{body.source_url}]",
        )
        if item
    )
    order = _create_order(
        db,
        supplier=supplier,
        crop=body.crop,
        variety=body.variety,
        quantity=body.quantity,
        unit=body.unit,
        unit_price_eur=unit_price,
        order_date=body.order_date,
        expected_date=body.expected_date,
        notes=notes,
    )
    return {
        "message": "Ponudba je dodana v GrowMaster Nabavo. Seme še NI na zalogi; ob dostavi uporabi PREVZEM SEMENA.",
        "purchase_order_id": order.id,
        "supplier_id": supplier.id,
        "supplier": supplier.name,
        "crop": body.crop,
        "variety": body.variety,
        "quantity": body.quantity,
        "unit": body.unit,
        "total_eur": round(body.total_price_eur, 2),
        "status": order.status,
        "inventory_changed": False,
    }


@router.get("/api/seed-inventory/purchase-orders/open")
def open_seed_purchase_orders(db: Session = Depends(get_db)) -> dict:
    orders = db.scalars(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.farm_id == DEFAULT_FARM_ID,
            PurchaseOrder.status == "ordered",
        )
        .options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.supply_item),
        )
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
    ).all()
    result = []
    for order in orders:
        marker = _seed_marker(order)
        if marker is None:
            continue
        crop, variety, unit = marker
        seed_items = [item for item in order.items if item.supply_item.category == "seed"]
        quantity = sum(item.quantity for item in seed_items)
        result.append(
            {
                "purchase_order_id": order.id,
                "supplier": order.supplier.name,
                "crop": crop,
                "variety": variety or None,
                "unit": unit,
                "ordered_quantity": quantity,
                "total_eur": round(sum(item.line_total_eur for item in seed_items), 2),
                "order_date": str(order.order_date),
                "expected_date": str(order.expected_date) if order.expected_date else None,
                "source_url": _seed_offer_url(order),
                "status": order.status,
            }
        )
    return {"orders": result, "count": len(result)}


@router.post("/api/seed-inventory/purchase-orders/{order_id}/receive")
def receive_seed_purchase_order(order_id: int, body: SeedPurchaseReceive, db: Session = Depends(get_db)) -> dict:
    order = _load_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Nabavno naročilo ne obstaja.")
    if order.status == "received":
        raise HTTPException(status_code=409, detail="Naročilo je že prevzeto.")
    if order.status == "cancelled":
        raise HTTPException(status_code=409, detail="Preklicanega naročila ni mogoče prevzeti.")
    marker = _seed_marker(order)
    if marker is None:
        raise HTTPException(status_code=409, detail="Naročilo nima GrowMaster seed metadata oznake.")
    crop, variety, unit = marker
    seed_items = [item for item in order.items if item.supply_item.category == "seed"]
    if not seed_items:
        raise HTTPException(status_code=409, detail="Naročilo nima semenske postavke.")
    ordered_quantity = sum(item.quantity for item in seed_items)
    received_quantity = body.received_quantity or ordered_quantity
    if body.received_quantity is not None and len(seed_items) != 1:
        raise HTTPException(
            status_code=409,
            detail="Dejanske količine ni mogoče samodejno razdeliti med več semenskih postavk.",
        )
    if len(seed_items) == 1:
        seed_items[0].supply_item.stock_quantity += received_quantity
    else:
        for item in seed_items:
            item.supply_item.stock_quantity += item.quantity
    try:
        lot = create_lot(
            {
                "crop": crop,
                "variety": variety or None,
                "supplier": order.supplier.name,
                "lot_number": body.lot_number,
                "unit": unit,
                "quantity": received_quantity,
                "package_size": body.package_size,
                "thousand_seed_weight_g": body.thousand_seed_weight_g,
                "germination_pct": body.germination_pct,
                "field_emergence_pct": body.field_emergence_pct,
                "purchase_date": str(order.order_date),
                "expiry_date": body.expiry_date,
                "notes": f"Prevzem iz GrowMaster PO #{order.id}; naročeno {ordered_quantity:g} {unit}, dejansko prejeto {received_quantity:g} {unit}.",
            }
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    order.status = "received"
    order.received_on = body.received_on
    db.commit()
    return {
        "message": "PREVZEM SEMENA je potrjen; fizična zaloga in Seed Inventory lot sta posodobljena.",
        "purchase_order_id": order.id,
        "ordered_quantity": ordered_quantity,
        "received_quantity": received_quantity,
        "unit": unit,
        "seed_lot": lot,
        "inventory_changed": True,
    }
