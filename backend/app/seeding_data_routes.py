from fastapi import APIRouter

from app.seeding_profiles import export_seeding_data, load_seeding_data, seeding_data_path


router = APIRouter()


@router.get("/api/system/seeding-data")
def seeding_data_status() -> dict:
    path = seeding_data_path()
    payload = load_seeding_data()
    return {
        "path": str(path),
        "external_file_exists": path.exists(),
        "schema_version": payload.get("schema_version"),
        "bed_width_cm": payload.get("bed_width_cm", 80),
        "profile_count": len(payload.get("profiles", {})),
        "message": (
            "GrowMaster uporablja zunanjo sejalniško podatkovno datoteko."
            if path.exists()
            else "GrowMaster trenutno uporablja vgrajeno predlogo; izvozi jo za urejanje brez spremembe aplikacije."
        ),
    }


@router.post("/api/system/seeding-data/export")
def export_seeding_master_data() -> dict:
    path = export_seeding_data()
    payload = load_seeding_data()
    return {
        "message": "Sejalniška master-data datoteka je pripravljena za urejanje.",
        "path": str(path),
        "profile_count": len(payload.get("profiles", {})),
        "note": "Spremembe datoteke se pri naslednjem izračunu preberejo samodejno; rebuild ni potreben.",
    }
