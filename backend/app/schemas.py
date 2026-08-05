from datetime import date

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
