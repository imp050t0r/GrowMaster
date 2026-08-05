from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Farm(Base):
    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)

    beds: Mapped[list["Bed"]] = relationship(back_populates="farm")
    tasks: Mapped[list["Task"]] = relationship(back_populates="farm")
    harvests: Mapped[list["Harvest"]] = relationship(back_populates="farm")
    costs: Mapped[list["Cost"]] = relationship(back_populates="farm")
    sales: Mapped[list["Sale"]] = relationship(back_populates="farm")
    customers: Mapped[list["Customer"]] = relationship(back_populates="farm")
    orders: Mapped[list["Order"]] = relationship(back_populates="farm")
    order_payments: Mapped[list["OrderPayment"]] = relationship(back_populates="farm")
    crop_plans: Mapped[list["CropPlan"]] = relationship(back_populates="farm")
    sales_settings: Mapped["SalesSettings | None"] = relationship(back_populates="farm")
    retail_sales: Mapped[list["RetailSale"]] = relationship(back_populates="farm")
    invoice_profile: Mapped["InvoiceProfile | None"] = relationship(back_populates="farm")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="farm")
    credit_notes: Mapped[list["CreditNote"]] = relationship(back_populates="farm")
    refunds: Mapped[list["Refund"]] = relationship(back_populates="farm")
    product_prices: Mapped[list["ProductPrice"]] = relationship(back_populates="farm")
    day_closes: Mapped[list["DayClose"]] = relationship(back_populates="farm")
    suppliers: Mapped[list["Supplier"]] = relationship(back_populates="farm")
    supply_items: Mapped[list["SupplyItem"]] = relationship(back_populates="farm")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="farm")
    supply_usages: Mapped[list["SupplyUsage"]] = relationship(back_populates="farm")
    supplier_payments: Mapped[list["SupplierPayment"]] = relationship(
        back_populates="farm"
    )


class Crop(Base):
    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    family: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(120))

    varieties: Mapped[list["Variety"]] = relationship(
        back_populates="crop", cascade="all, delete-orphan"
    )
    product_prices: Mapped[list["ProductPrice"]] = relationship(back_populates="crop")


class Variety(Base):
    __tablename__ = "varieties"

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    days_to_harvest: Mapped[int]

    crop: Mapped[Crop] = relationship(back_populates="varieties")


class Bed(Base):
    __tablename__ = "beds"
    __table_args__ = (UniqueConstraint("farm_id", "name", name="uq_bed_farm_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(40), index=True)
    width_m: Mapped[float] = mapped_column(Float)
    length_m: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="empty")
    last_crop_family: Mapped[str | None] = mapped_column(String(120), nullable=True)

    farm: Mapped[Farm] = relationship(back_populates="beds")
    plantings: Mapped[list["Planting"]] = relationship(back_populates="bed")
    tasks: Mapped[list["Task"]] = relationship(back_populates="bed")
    harvests: Mapped[list["Harvest"]] = relationship(back_populates="bed")
    costs: Mapped[list["Cost"]] = relationship(back_populates="bed")
    crop_plans: Mapped[list["CropPlan"]] = relationship(back_populates="bed")
    supply_usages: Mapped[list["SupplyUsage"]] = relationship(back_populates="bed")

    @property
    def area_m2(self) -> float:
        return round(self.width_m * self.length_m, 2)


class Planting(Base):
    __tablename__ = "plantings"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    bed_id: Mapped[int] = mapped_column(ForeignKey("beds.id", ondelete="RESTRICT"))
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="RESTRICT"))
    variety_id: Mapped[int] = mapped_column(ForeignKey("varieties.id", ondelete="RESTRICT"))
    sowing_date: Mapped[date] = mapped_column(Date)
    expected_harvest_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    rotation_override: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    bed: Mapped[Bed] = relationship(back_populates="plantings")
    crop: Mapped[Crop] = relationship()
    variety: Mapped[Variety] = relationship()
    tasks: Mapped[list["Task"]] = relationship(back_populates="planting")
    harvests: Mapped[list["Harvest"]] = relationship(back_populates="planting")
    costs: Mapped[list["Cost"]] = relationship(back_populates="planting")
    supply_usages: Mapped[list["SupplyUsage"]] = relationship(
        back_populates="planting"
    )


class Harvest(Base):
    __tablename__ = "harvests"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    bed_id: Mapped[int] = mapped_column(ForeignKey("beds.id", ondelete="RESTRICT"), index=True)
    planting_id: Mapped[int] = mapped_column(ForeignKey("plantings.id", ondelete="RESTRICT"), index=True)
    harvest_date: Mapped[date] = mapped_column(Date, index=True)
    quantity_kg: Mapped[float] = mapped_column(Float)
    quality: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="harvests")
    bed: Mapped[Bed] = relationship(back_populates="harvests")
    planting: Mapped[Planting] = relationship(back_populates="harvests")
    sales: Mapped[list["Sale"]] = relationship(back_populates="harvest")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="harvest")
    retail_sale_items: Mapped[list["RetailSaleItem"]] = relationship(back_populates="harvest")


class Cost(Base):
    __tablename__ = "costs"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    bed_id: Mapped[int] = mapped_column(ForeignKey("beds.id", ondelete="RESTRICT"), index=True)
    planting_id: Mapped[int | None] = mapped_column(ForeignKey("plantings.id", ondelete="SET NULL"), nullable=True, index=True)
    cost_date: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(40))
    amount_eur: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="costs")
    bed: Mapped[Bed] = relationship(back_populates="costs")
    planting: Mapped[Planting | None] = relationship(back_populates="costs")


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    harvest_id: Mapped[int] = mapped_column(ForeignKey("harvests.id", ondelete="RESTRICT"), index=True)
    sale_date: Mapped[date] = mapped_column(Date, index=True)
    quantity_kg: Mapped[float] = mapped_column(Float)
    price_per_kg_eur: Mapped[float] = mapped_column(Float)
    customer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="sales")
    harvest: Mapped[Harvest] = relationship(back_populates="sales")

    @property
    def revenue_eur(self) -> float:
        return round(self.quantity_kg * self.price_per_kg_eur, 2)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("farm_id", "name", name="uq_customer_farm_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="customers")
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    profile: Mapped["CustomerProfile | None"] = relationship(back_populates="customer")
    retail_sales: Mapped[list["RetailSale"]] = relationship(back_populates="customer")


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True
    )
    customer_type: Mapped[str] = mapped_column(String(20), default="consumer", index=True)
    tax_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="profile")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    order_date: Mapped[date] = mapped_column(Date, index=True)
    delivery_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30), default="confirmed", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="orders")
    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[list["OrderPayment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    invoice: Mapped["Invoice | None"] = relationship(back_populates="order", uselist=False)

    @property
    def total_eur(self) -> float:
        return round(sum(item.line_total_eur for item in self.items), 2)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    harvest_id: Mapped[int] = mapped_column(ForeignKey("harvests.id", ondelete="RESTRICT"), index=True)
    quantity_kg: Mapped[float] = mapped_column(Float)
    price_per_kg_eur: Mapped[float] = mapped_column(Float)

    order: Mapped[Order] = relationship(back_populates="items")
    harvest: Mapped[Harvest] = relationship(back_populates="order_items")

    @property
    def line_total_eur(self) -> float:
        return round(self.quantity_kg * self.price_per_kg_eur, 2)


class OrderPayment(Base):
    __tablename__ = "order_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    payment_date: Mapped[date] = mapped_column(Date, index=True)
    amount_eur: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="order_payments")
    order: Mapped[Order] = relationship(back_populates="payments")


class CropPlan(Base):
    __tablename__ = "crop_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    bed_id: Mapped[int] = mapped_column(ForeignKey("beds.id", ondelete="RESTRICT"), index=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="RESTRICT"), index=True)
    variety_id: Mapped[int] = mapped_column(ForeignKey("varieties.id", ondelete="RESTRICT"), index=True)
    planting_id: Mapped[int | None] = mapped_column(
        ForeignKey("plantings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    series_id: Mapped[str] = mapped_column(String(36), index=True)
    sowing_date: Mapped[date] = mapped_column(Date, index=True)
    transplant_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    expected_harvest_date: Mapped[date] = mapped_column(Date, index=True)
    expected_yield_kg: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="crop_plans")
    bed: Mapped[Bed] = relationship(back_populates="crop_plans")
    crop: Mapped[Crop] = relationship()
    variety: Mapped[Variety] = relationship()
    planting: Mapped[Planting | None] = relationship()


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("farm_id", "name", name="uq_supplier_farm_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), index=True)
    tax_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="suppliers")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        back_populates="supplier"
    )


class SupplyItem(Base):
    __tablename__ = "supply_items"
    __table_args__ = (
        UniqueConstraint("farm_id", "name", name="uq_supply_item_farm_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    unit: Mapped[str] = mapped_column(String(20))
    stock_quantity: Mapped[float] = mapped_column(Float, default=0)
    reorder_level: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="supply_items")
    purchase_order_items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="supply_item"
    )
    usages: Mapped[list["SupplyUsage"]] = relationship(back_populates="supply_item")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    order_date: Mapped[date] = mapped_column(Date, index=True)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    received_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ordered", index=True)
    payment_method: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="purchase_orders")
    supplier: Mapped[Supplier] = relationship(back_populates="purchase_orders")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )
    payments: Mapped[list["SupplierPayment"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )

    @property
    def total_eur(self) -> float:
        return round(sum(item.line_total_eur for item in self.items), 2)


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    supply_item_id: Mapped[int] = mapped_column(
        ForeignKey("supply_items.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[float] = mapped_column(Float)
    unit_price_eur: Mapped[float] = mapped_column(Float)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")
    supply_item: Mapped[SupplyItem] = relationship(
        back_populates="purchase_order_items"
    )

    @property
    def line_total_eur(self) -> float:
        return round(self.quantity * self.unit_price_eur, 2)


class SupplyUsage(Base):
    __tablename__ = "supply_usages"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    supply_item_id: Mapped[int] = mapped_column(
        ForeignKey("supply_items.id", ondelete="RESTRICT"), index=True
    )
    bed_id: Mapped[int] = mapped_column(
        ForeignKey("beds.id", ondelete="RESTRICT"), index=True
    )
    planting_id: Mapped[int | None] = mapped_column(
        ForeignKey("plantings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    usage_date: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[float] = mapped_column(Float)
    unit_cost_eur: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="supply_usages")
    supply_item: Mapped[SupplyItem] = relationship(back_populates="usages")
    bed: Mapped[Bed] = relationship(back_populates="supply_usages")
    planting: Mapped[Planting | None] = relationship(back_populates="supply_usages")

    @property
    def total_cost_eur(self) -> float:
        return round(self.quantity * self.unit_cost_eur, 2)


class SupplierPayment(Base):
    __tablename__ = "supplier_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    payment_date: Mapped[date] = mapped_column(Date, index=True)
    amount_eur: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="supplier_payments")
    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="payments")


class ProductPrice(Base):
    __tablename__ = "product_prices"
    __table_args__ = (
        UniqueConstraint(
            "farm_id", "crop_id", "quality", name="uq_product_price"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    crop_id: Mapped[int] = mapped_column(
        ForeignKey("crops.id", ondelete="RESTRICT"), index=True
    )
    quality: Mapped[str] = mapped_column(String(20))
    price_per_kg_eur: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    farm: Mapped[Farm] = relationship(back_populates="product_prices")
    crop: Mapped[Crop] = relationship(back_populates="product_prices")


class DayClose(Base):
    __tablename__ = "day_closes"
    __table_args__ = (
        UniqueConstraint("farm_id", "business_date", name="uq_day_close"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    business_date: Mapped[date] = mapped_column(Date, index=True)
    opening_cash_eur: Mapped[float] = mapped_column(Float)
    cash_in_eur: Mapped[float] = mapped_column(Float)
    cash_refund_eur: Mapped[float] = mapped_column(Float)
    card_in_eur: Mapped[float] = mapped_column(Float)
    card_refund_eur: Mapped[float] = mapped_column(Float)
    bank_transfer_in_eur: Mapped[float] = mapped_column(Float)
    bank_transfer_refund_eur: Mapped[float] = mapped_column(Float)
    total_inflow_eur: Mapped[float] = mapped_column(Float)
    total_refund_eur: Mapped[float] = mapped_column(Float)
    expected_cash_eur: Mapped[float] = mapped_column(Float)
    counted_cash_eur: Mapped[float] = mapped_column(Float)
    difference_eur: Mapped[float] = mapped_column(Float)
    retail_sale_count: Mapped[int] = mapped_column(Integer)
    payment_count: Mapped[int] = mapped_column(Integer)
    refund_count: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="day_closes")
    supplier_payment_snapshot: Mapped["DayCloseSupplierPaymentSnapshot | None"] = (
        relationship(
            back_populates="day_close",
            cascade="all, delete-orphan",
            uselist=False,
        )
    )


class DayCloseSupplierPaymentSnapshot(Base):
    __tablename__ = "day_close_supplier_payment_snapshots"

    day_close_id: Mapped[int] = mapped_column(
        ForeignKey("day_closes.id", ondelete="CASCADE"), primary_key=True
    )
    cash_out_eur: Mapped[float] = mapped_column(Float, default=0)
    card_out_eur: Mapped[float] = mapped_column(Float, default=0)
    bank_transfer_out_eur: Mapped[float] = mapped_column(Float, default=0)
    payment_count: Mapped[int] = mapped_column(Integer, default=0)

    day_close: Mapped[DayClose] = relationship(
        back_populates="supplier_payment_snapshot"
    )


class SalesSettings(Base):
    __tablename__ = "sales_settings"

    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), primary_key=True
    )
    basic_agriculture_invoice_exemption: Mapped[bool] = mapped_column(Boolean, default=True)
    seller_name: Mapped[str] = mapped_column(String(160), default="GrowMaster kmetija")
    seller_tax_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    farm: Mapped[Farm] = relationship(back_populates="sales_settings")


class InvoiceProfile(Base):
    __tablename__ = "invoice_profiles"

    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), primary_key=True
    )
    seller_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_iban: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seller_registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vat_note: Mapped[str | None] = mapped_column(String(240), nullable=True)
    business_premise_code: Mapped[str] = mapped_column(String(20), default="GM")
    device_code: Mapped[str] = mapped_column(String(20), default="01")
    default_due_days: Mapped[int] = mapped_column(Integer, default=14)

    farm: Mapped[Farm] = relationship(back_populates="invoice_profile")


class DocumentSequence(Base):
    __tablename__ = "document_sequences"
    __table_args__ = (
        UniqueConstraint(
            "farm_id", "year", "document_type", name="uq_document_sequence"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    year: Mapped[int] = mapped_column(Integer)
    document_type: Mapped[str] = mapped_column(String(20))
    next_number: Mapped[int] = mapped_column(Integer, default=1)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True, unique=True
    )
    retail_sale_id: Mapped[int | None] = mapped_column(
        ForeignKey("retail_sales.id", ondelete="RESTRICT"), nullable=True, unique=True
    )
    number: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    issued_on: Mapped[date] = mapped_column(Date, index=True)
    supply_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="issued", index=True)
    payment_method: Mapped[str] = mapped_column(String(20))
    seller_name: Mapped[str] = mapped_column(String(160))
    seller_address: Mapped[str] = mapped_column(Text)
    seller_tax_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    seller_iban: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seller_registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vat_note: Mapped[str | None] = mapped_column(String(240), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(160))
    customer_address: Mapped[str] = mapped_column(Text)
    customer_tax_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    total_eur: Mapped[float] = mapped_column(Float)
    fiscal_confirmation_required: Mapped[bool] = mapped_column(Boolean, default=False)
    eor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    zoi: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pdf_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="invoices")
    order: Mapped[Order | None] = relationship(back_populates="invoice")
    retail_sale: Mapped["RetailSale | None"] = relationship(back_populates="invoice")
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLine.id"
    )
    credit_note: Mapped["CreditNote | None"] = relationship(
        back_populates="invoice", uselist=False
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(String(240))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20), default="kg")
    unit_price_eur: Mapped[float] = mapped_column(Float)
    line_total_eur: Mapped[float] = mapped_column(Float)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")


class CreditNote(Base):
    __tablename__ = "credit_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), unique=True, index=True
    )
    number: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    issued_on: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str] = mapped_column(String(500))
    total_eur: Mapped[float] = mapped_column(Float)
    fiscal_confirmation_required: Mapped[bool] = mapped_column(Boolean, default=False)
    eor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    zoi: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pdf_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="credit_notes")
    invoice: Mapped[Invoice] = relationship(back_populates="credit_note")
    refunds: Mapped[list["Refund"]] = relationship(
        back_populates="credit_note", cascade="all, delete-orphan"
    )


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    credit_note_id: Mapped[int] = mapped_column(
        ForeignKey("credit_notes.id", ondelete="RESTRICT"), index=True
    )
    refund_date: Mapped[date] = mapped_column(Date, index=True)
    amount_eur: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="refunds")
    credit_note: Mapped[CreditNote] = relationship(back_populates="refunds")


class RetailSale(Base):
    __tablename__ = "retail_sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sale_date: Mapped[date] = mapped_column(Date, index=True)
    payment_method: Mapped[str] = mapped_column(String(20), default="cash")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="retail_sales")
    customer: Mapped[Customer | None] = relationship(back_populates="retail_sales")
    items: Mapped[list["RetailSaleItem"]] = relationship(
        back_populates="retail_sale", cascade="all, delete-orphan"
    )
    invoice: Mapped["Invoice | None"] = relationship(
        back_populates="retail_sale", uselist=False
    )

    @property
    def total_eur(self) -> float:
        return round(sum(item.line_total_eur for item in self.items), 2)


class RetailSaleItem(Base):
    __tablename__ = "retail_sale_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    retail_sale_id: Mapped[int] = mapped_column(
        ForeignKey("retail_sales.id", ondelete="CASCADE"), index=True
    )
    harvest_id: Mapped[int] = mapped_column(
        ForeignKey("harvests.id", ondelete="RESTRICT"), index=True
    )
    quantity_kg: Mapped[float] = mapped_column(Float)
    price_per_kg_eur: Mapped[float] = mapped_column(Float)

    retail_sale: Mapped[RetailSale] = relationship(back_populates="items")
    harvest: Mapped[Harvest] = relationship(back_populates="retail_sale_items")

    @property
    def line_total_eur(self) -> float:
        return round(self.quantity_kg * self.price_per_kg_eur, 2)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    bed_id: Mapped[int | None] = mapped_column(
        ForeignKey("beds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    planting_id: Mapped[int | None] = mapped_column(
        ForeignKey("plantings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    task_type: Mapped[str] = mapped_column(String(50), default="general")
    due_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="tasks")
    bed: Mapped[Bed | None] = relationship(back_populates="tasks")
    planting: Mapped[Planting | None] = relationship(back_populates="tasks")
