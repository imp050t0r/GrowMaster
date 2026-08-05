from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
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
    crop_plans: Mapped[list["CropPlan"]] = relationship(back_populates="farm")


class Crop(Base):
    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    family: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(120))

    varieties: Mapped[list["Variety"]] = relationship(
        back_populates="crop", cascade="all, delete-orphan"
    )


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
