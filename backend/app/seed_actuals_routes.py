from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.seed_inventory_service import load_inventory, save_inventory

router = APIRouter()


class ActualSeedUse(BaseModel):
    quantity: float = Field(gt=0, le=1_000_000)
    unit: str = Field(pattern="^(g|seeds|pellets)$")
    note: str | None = Field(default=None, max_length=500)


@router.post("/api/seed-inventory/plantings/{planting_id}/actual-seed-use")
def record_actual_seed_use(planting_id: int, body: ActualSeedUse) -> dict:
    payload = load_inventory()
    record = next((item for item in payload.get("planting_consumptions", []) if int(item.get("planting_id", -1)) == planting_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Za to setev ni inventarnega zapisa.")
    record["actual_seed_use"] = {
        "quantity": body.quantity,
        "unit": body.unit,
        "note": body.note,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    save_inventory(payload)
    return {"message": "Dejanska poraba semena je zapisana in bo uporabljena pri učnih analizah.", "planting_id": planting_id, "actual_seed_use": record["actual_seed_use"]}
