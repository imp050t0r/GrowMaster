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


class CropCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    family: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)


class VarietyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    days_to_harvest: int = Field(ge=1, le=730)


class BedCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    width_m: float = Field(gt=0, le=100)
    length_m: float = Field(gt=0, le=1000)


class BedSizeUpdate(BaseModel):
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
    worker_id: int | None = None
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


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    tax_number: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=2000)


class SupplyItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: Literal["seed", "fertilizer", "packaging", "tools", "fuel", "other"]
    unit: str = Field(min_length=1, max_length=20)
    opening_stock: float = Field(default=0, ge=0, le=1000000)
    reorder_level: float = Field(default=0, ge=0, le=1000000)


class PurchaseOrderItemCreate(BaseModel):
    supply_item_id: int
    quantity: float = Field(gt=0, le=1000000)
    unit_price_eur: float = Field(gt=0, le=1000000)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    order_date: date
    expected_date: date | None = None
    payment_method: Literal["cash", "card", "bank_transfer"] = "bank_transfer"
    notes: str | None = Field(default=None, max_length=2000)
    items: list[PurchaseOrderItemCreate] = Field(min_length=1, max_length=100)


class PurchaseOrderReceive(BaseModel):
    received_on: date


class SupplyUsageCreate(BaseModel):
    supply_item_id: int
    bed_id: int
    planting_id: int | None = None
    usage_date: date
    quantity: float = Field(gt=0, le=1000000)
    unit_cost_eur: float | None = Field(default=None, gt=0, le=1000000)
    notes: str | None = Field(default=None, max_length=2000)


class SupplierPaymentCreate(BaseModel):
    payment_date: date
    amount_eur: float = Field(gt=0, le=1000000)
    payment_method: Literal["cash", "card", "bank_transfer"]
    notes: str | None = Field(default=None, max_length=2000)


class WorkerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=120)
    hourly_rate_eur: float = Field(ge=0, le=100000)


class LaborEntryCreate(BaseModel):
    worker_id: int
    bed_id: int | None = None
    planting_id: int | None = None
    work_date: date
    duration_minutes: int = Field(gt=0, le=1440)
    hourly_rate_eur: float | None = Field(default=None, ge=0, le=100000)
    description: str = Field(min_length=1, max_length=200)


class FarmExpenseCreate(BaseModel):
    expense_date: date
    category: Literal[
        "fuel",
        "utilities",
        "rent",
        "insurance",
        "maintenance",
        "administration",
        "other",
    ]
    amount_eur: float = Field(gt=0, le=1000000)
    payment_method: Literal["cash", "card", "bank_transfer"]
    supplier: str | None = Field(default=None, max_length=160)
    reference: str | None = Field(default=None, max_length=120)
    description: str = Field(min_length=1, max_length=200)


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


class AuthSetup(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    farm_name: str = Field(min_length=1, max_length=120)
    keep_demo_data: bool = False
    password: str = Field(min_length=12, max_length=256)


class AuthLogin(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class AccountUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    current_password: str = Field(min_length=1, max_length=256)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class FarmProfileUpdate(BaseModel):
    farm_name: str = Field(min_length=1, max_length=120)
    basic_agriculture_invoice_exemption: bool = True
    seller_tax_number: str | None = Field(default=None, max_length=30)
    seller_address: str = Field(default="", max_length=1000)
    seller_iban: str | None = Field(default=None, max_length=50)
    seller_registration_number: str | None = Field(default=None, max_length=50)
    vat_note: str | None = Field(default=None, max_length=240)
    business_premise_code: str = Field(default="GM", min_length=1, max_length=20)
    device_code: str = Field(default="01", min_length=1, max_length=20)
    default_due_days: int = Field(default=14, ge=0, le=365)
