"""Build the public, checksummed GrowMaster Plant DB update bundle."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.maturity import estimated_seasonal_days  # noqa: E402
from app.south_asian_requested_crops import SOUTH_ASIAN_REQUESTED_CROPS  # noqa: E402


OUTPUT = ROOT / "plant-db" / "latest"
VERSION = "2026.08.26.1"


def write_json(path: Path, payload: dict) -> None:
    # Keep release bytes identical on Windows, macOS, Linux, and GitHub raw.
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def copy_json(source: Path, target: Path) -> None:
    data = source.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    json.loads(data.decode("utf-8"))
    target.write_bytes(data)


def build_crops() -> dict:
    groups: dict[str, dict] = {}
    metadata_fields = (
        "source_name", "source_url", "seed_forms", "traits", "slovenia_note",
        "days_baby", "seed_rate_g_m2", "seed_spacing_cm", "row_spacing_cm",
        "planting_method", "outdoor_months", "protected_months", "heat_tolerance",
        "cold_tolerance", "planting_calendar_note", "succession_interval_days",
        "calendar_source_url", "cultivation_methods", "harvest_methods", "nursery_days",
        "direct_sow_extra_days", "days_outer_leaf", "regrowth_interval_min_days",
        "regrowth_interval_max_days", "max_regrowth_cuts", "days_green_harvest",
        "harvest_interval_days", "harvest_duration_days", "harvest_profile_note",
        "harvest_source_url",
    )
    for item in SOUTH_ASIAN_REQUESTED_CROPS:
        group = groups.setdefault(item["crop"], {
            "name": item["crop"], "family": item["family"],
            "category": item["category"], "varieties": [],
        })
        seasonal = estimated_seasonal_days(item["days"])
        group["varieties"].append({
            "name": item["name"], "days_to_harvest": item["days"],
            "days_spring": seasonal["spring"], "days_summer": seasonal["summer"],
            "days_autumn": seasonal["autumn"], "days_winter": seasonal["winter"],
            "composition": None,
            **{field: item[field] for field in metadata_fields},
        })
    return {"schema_version": 1, "crops": sorted(groups.values(), key=lambda item: item["name"])}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = {
        "crops": "growmaster-crops.json",
        "seeding": "growmaster-seeding.json",
        "rollers": "growmaster-rollers.json",
        "rotation": "growmaster-rotation.json",
    }
    write_json(OUTPUT / files["crops"], build_crops())
    copy_json(ROOT / "backend/app/data/seeding_profiles.json", OUTPUT / files["seeding"])
    copy_json(ROOT / "backend/app/data/roller_catalog.json", OUTPUT / files["rollers"])
    copy_json(ROOT / "backend/app/data/rotation_rules.json", OUTPUT / files["rotation"])
    manifest = {
        "schema_version": 1,
        "plant_db_version": VERSION,
        "minimum_app_version": "1.24.2",
        "files": {
            name: {
                "path": filename,
                "sha256": hashlib.sha256((OUTPUT / filename).read_bytes()).hexdigest(),
            }
            for name, filename in files.items()
        },
    }
    write_json(OUTPUT / "manifest.json", manifest)
    print(f"Plant DB {VERSION}: {len(build_crops()['crops'])} crop groups")


if __name__ == "__main__":
    main()
