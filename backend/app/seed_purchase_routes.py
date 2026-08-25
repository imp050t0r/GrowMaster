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


class SeedPurchaseReceive(BaseModel):
    received_on: date = Field(default_factory=date.today)
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
        .options(selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.supply_item))
    )


@router.post("/api/seed-inventory/purchase-orders", status_code=status.HTTP_201_CREATED)
def create_seed_purchase_order(body: SeedPurchaseCreate, db: Session = Depends(get_db)) -> dict:
    supplier = db.scalar(select(Supplier).where(Supplier.id == body.supplier_id, Supplier.farm_id == DEFAULT_FARM_ID))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Dobavitelj ne obstaja.")
    item_name = f"Seme – {body.crop} {body.variety or ''}".strip()
    supply_item = db.scalar(select(SupplyItem).where(SupplyItem.farm_id == DEFAULT_FARM_ID, SupplyItem.name == item_name))
    if supply_item is None:
        supply_item = SupplyItem(farm_id=DEFAULT_FARM_ID, name=item_name, category="seed", unit=body.unit, stock_quantity=0, reorder_level=0)
        db.add(supply_item)
        db.flush()
    elif supply_item.unit != body.unit:
        raise HTTPException(status_code=409, detail=f"Material {item_name} že uporablja enoto {supply_item.unit}; naročilo uporablja {body.unit}.")
    order = PurchaseOrder(
        farm_id=DEFAULT_FARM_ID,
        supplier_id=supplier.id,
        order_date=body.order_date,
        expected_date=body.expected_date,
        received_on=None,
        status="ordered",
        payment_method="bank_transfer",
        notes=(body.notes or "") + f"\n[seed:{body.crop}|{body.variety or ''}|{body.unit}]",
    )
    db.add(order)
    db.flush()
    order.items.append(PurchaseOrderItem(supply_item_id=supply_item.id, quantity=body.quantity, unit_price_eur=body.unit_price_eur))
    db.commit()
    db.refresh(order)
    return {
        "message": "Semensko naročilo je ustvarjeno v GrowMaster Nabavi.",
        "purchase_order_id": order.id,
        "supplier": supplier.name,
        "crop": body.crop,
        "variety": body.variety,
        "quantity": body.quantity,
        "unit": body.unit,
        "total_eur": round(body.quantity * body.unit_price_eur, 2),
        "status": order.status,
    }


@router.post("/api/seed-inventory/purchase-orders/{order_id}/receive")
def receive_seed_purchase_order(order_id: int, body: SeedPurchaseReceive, db: Session = Depends(get_db)) -> dict:
    order = _load_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Nabavno naročilo ne obstaja.")
    if order.status == "received":
        raise HTTPException(status_code=409, detail="Naročilo je že prevzeto.")
    if order.status == "cancelled":
        raise HTTPException(status_code=409, detail="Preklicanega naročila ni mogoče prevzeti.")
    marker = next((line for line in (order.notes or "").splitlines() if line.startswith("[seed:") and line.endswith("]")), None)
    if marker is None:
        raise HTTPException(status_code=409, detail="Naročilo nima GrowMaster seed metadata oznake.")
    crop, variety, unit = marker[6:-1].split("|", 2)
    total_quantity = 0.0
    for item in order.items:
        if item.supply_item.category != "seed":
            continue
        item.supply_item.stock_quantity += item.quantity
        total_quantity += item.quantity
    if total_quantity <= 0:
        raise HTTPException(status_code=409, detail="Naročilo nima semenske postavke.")
    try:
        lot = create_lot({
            "crop": crop,
            "variety": variety or None,
            "supplier": order.supplier.name,
            "lot_number": body.lot_number,
            "unit": unit,
            "quantity": total_quantity,
            "package_size": body.package_size,
            "thousand_seed_weight_g": body.thousand_seed_weight_g,
            "germination_pct": body.germination_pct,
            "field_emergence_pct": body.field_emergence_pct,
            "purchase_date": str(order.order_date),
            "expiry_date": body.expiry_date,
            "notes": f"Prevzem iz GrowMaster PO #{order.id}",
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    order.status = "received"
    order.received_on = body.received_on
    db.commit()
    return {"message": "Semensko naročilo je prevzeto; zaloga materiala in Seed Inventory sta posodobljena.", "purchase_order_id": order.id, "seed_lot": lot}
