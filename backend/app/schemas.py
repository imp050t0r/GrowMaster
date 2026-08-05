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
