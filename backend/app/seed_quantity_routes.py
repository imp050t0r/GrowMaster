from fastapi import APIRouter, HTTPException, Query

from app.seed_quantity import calculate_seed_quantity
from app.seeding_profiles import seeding_profile


router = APIRouter()


@router.get("/api/seeding/quantity")
def seed_quantity(
    crop: str = Query(min_length=1),
    variety: str | None = None,
    family: str | None = None,
    category: str | None = None,
    bed_width_m: float = Query(default=0.8, gt=0, le=10),
    bed_length_m: float = Query(default=15.0, gt=0, le=1000),
    bed_count: int = Query(default=1, ge=1, le=10000),
    reserve_percent: float = Query(default=5.0, ge=0, le=100),
) -> dict:
    profile = seeding_profile(crop, variety, family, category)
    result = calculate_seed_quantity(
        profile.get("seed_rate_g_m2"),
        bed_width_m,
        bed_length_m,
        bed_count,
        reserve_percent,
    )
    if not result["available"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": result["note"],
                "crop": crop,
                "variety": variety,
                "seeding": profile,
                "calculation": result,
            },
        )
    return {
        "crop": crop,
        "variety": variety,
        "seeding": profile,
        "calculation": result,
    }
