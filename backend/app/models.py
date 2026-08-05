from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Farm(Base):
    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)

    beds: Mapped[list["Bed"]] = relationship(back_populates="farm")


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

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(40), index=True)
    width_m: Mapped[float] = mapped_column(Float)
    length_m: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="empty")
    last_crop_family: Mapped[str | None] = mapped_column(String(120), nullable=True)

    farm: Mapped[Farm] = relationship(back_populates="beds")
    plantings: Mapped[list["Planting"]] = relationship(back_populates="bed")

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
