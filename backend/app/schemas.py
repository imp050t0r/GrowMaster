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
    customer_type: Literal["consumer", "business"] = "consumer"
    tax_number: str | None = Field(default=None, max_length=30)


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


class OrderPaymentCreate(BaseModel):
    payment_date: date
    amount_eur: float = Field(gt=0, le=1000000)
    payment_method: Literal["cash", "card", "bank_transfer"]
    notes: str | None = Field(default=None, max_length=2000)


class CropPlanCreate(BaseModel):
    bed_id: int
    crop_id: int
    variety_id: int
    sowing_date: date
    transplant_date: date | None = None
    expected_yield_kg: float = Field(gt=0, le=100000)
    succession_count: int = Field(default=1, ge=1, le=20)
    succession_interval_days: int = Field(default=14, ge=1, le=365)
    notes: str | None = Field(default=None, max_length=2000)


class CropPlanActivate(BaseModel):
    override_rotation: bool = False


class CropPlanStatusUpdate(BaseModel):
    status: Literal["cancelled"]


class RetailSaleItemCreate(BaseModel):
    harvest_id: int
    quantity_kg: float = Field(gt=0, le=100000)
    price_per_kg_eur: float = Field(gt=0, le=100000)


class RetailSaleCreate(BaseModel):
    customer_id: int | None = None
    sale_date: date
    payment_method: Literal["cash", "card", "bank_transfer"] = "cash"
    notes: str | None = Field(default=None, max_length=2000)
    items: list[RetailSaleItemCreate] = Field(min_length=1, max_length=100)


class ProductPriceUpdate(BaseModel):
    quality: Literal["A", "B"]
    price_per_kg_eur: float = Field(gt=0, le=100000)


class DayCloseCreate(BaseModel):
    business_date: date
    opening_cash_eur: float = Field(ge=0, le=1000000)
    counted_cash_eur: float = Field(ge=0, le=1000000)
    notes: str | None = Field(default=None, max_length=2000)


class SalesSettingsUpdate(BaseModel):
    basic_agriculture_invoice_exemption: bool = True
    seller_name: str = Field(min_length=1, max_length=160)
    seller_tax_number: str | None = Field(default=None, max_length=30)


class InvoiceProfileUpdate(BaseModel):
    seller_address: str = Field(min_length=1, max_length=1000)
    seller_iban: str | None = Field(default=None, max_length=50)
    seller_registration_number: str | None = Field(default=None, max_length=50)
    vat_note: str | None = Field(default=None, max_length=240)
    business_premise_code: str = Field(default="GM", min_length=1, max_length=20)
    device_code: str = Field(default="01", min_length=1, max_length=20)
    default_due_days: int = Field(default=14, ge=0, le=365)


class InvoiceCreate(BaseModel):
    source_type: Literal["order", "retail_sale"]
    source_id: int
    issued_on: date
    due_date: date | None = None
    payment_method: Literal["cash", "card", "bank_transfer"] | None = None


class FiscalConfirmationCreate(BaseModel):
    eor: str = Field(min_length=1, max_length=80)
    zoi: str | None = Field(default=None, max_length=80)


class CreditNoteCreate(BaseModel):
    issued_on: date
    reason: str = Field(min_length=3, max_length=500)


class RefundCreate(BaseModel):
    refund_date: date
    amount_eur: float = Field(gt=0, le=1000000)
    payment_method: Literal["cash", "card", "bank_transfer"]
    notes: str | None = Field(default=None, max_length=2000)
