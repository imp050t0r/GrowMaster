from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VarietyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    days_to_harvest: int


class CropOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    family: str
    category: str
    varieties: list[VarietyOut]


class BedCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    width_m: float = Field(gt=0, le=100)
    length_m: float = Field(gt=0, le=1000)


class PlantingCreate(BaseModel):
    crop_id: int
    variety_id: int
    bed_id: int
    sowing_date: date
    override_rotation: bool = False


class RotationPreview(BaseModel):
    allowed: bool
    requires_override: bool = False
    code: str | None = None
    message: str
    warnings: list[str] = Field(default_factory=list)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    task_type: str = Field(default="general", min_length=1, max_length=50)
    due_date: date
    bed_id: int | None = None
    planting_id: int | None = None
    priority: Literal["low", "normal", "high"] = "normal"


class TaskComplete(BaseModel):
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    quantity_used: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)


class HarvestCreate(BaseModel):
    planting_id: int
    harvest_date: date
    quantity_kg: float = Field(gt=0, le=100000)
    quality: Literal["A", "B", "waste"]
    notes: str | None = Field(default=None, max_length=2000)


class CostCreate(BaseModel):
    bed_id: int
    planting_id: int | None = None
    cost_date: date
    category: Literal["seed", "labor", "fertilizer", "water", "packaging", "other"]
    amount_eur: float = Field(gt=0, le=1000000)
    description: str = Field(min_length=1, max_length=200)


class SaleCreate(BaseModel):
    harvest_id: int
    sale_date: date
    quantity_kg: float = Field(gt=0, le=100000)
    price_per_kg_eur: float = Field(gt=0, le=100000)
    customer: str | None = Field(default=None, max_length=120)


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=60)
    address: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)


class OrderItemCreate(BaseModel):
    harvest_id: int
    quantity_kg: float = Field(gt=0, le=100000)
    price_per_kg_eur: float = Field(gt=0, le=100000)


class OrderCreate(BaseModel):
    customer_id: int
    order_date: date
    delivery_date: date
    notes: str | None = Field(default=None, max_length=2000)
    items: list[OrderItemCreate] = Field(min_length=1, max_length=100)


class OrderStatusUpdate(BaseModel):
    status: Literal["fulfilled", "cancelled"]
