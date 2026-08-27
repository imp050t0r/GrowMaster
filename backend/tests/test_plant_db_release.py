import hashlib
import json
from pathlib import Path

from app.eu_leafy_crops import EU_LEAFY_CROPS


ROOT = Path(__file__).resolve().parents[2]


def test_dandelion_has_separate_standard_and_baby_leaf_profiles():
    dandelion = next(item for item in EU_LEAFY_CROPS if item["crop"] == "Regrat")
    baby = next(item for item in EU_LEAFY_CROPS if item["crop"] == "Baby leaf regrat")

    assert dandelion["english_name"] == "Dandelion"
    assert dandelion["botanical_name"] == "Taraxacum officinale"
    assert dandelion["family"] == "Asteraceae"
    assert dandelion["category"] == "Listnata"
    assert dandelion["source_name"].endswith("EU")
    assert "outer_leaves" in dandelion["harvest_methods"].split(",")
    assert "baby_leaf" not in dandelion["harvest_methods"].split(",")

    assert baby["source_name"].endswith("EU")
    assert baby["days"] == 30
    assert baby["days_baby"] == 30
    assert "baby_leaf" in baby["harvest_methods"].split(",")


def test_public_plant_db_release_contains_dandelion_and_matches_manifest():
    release = ROOT / "plant-db" / "latest"
    crops_path = release / "growmaster-crops.json"
    payload = json.loads(crops_path.read_text(encoding="utf-8"))
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    dandelion = next(crop for crop in payload["crops"] if crop["name"] == "Regrat")
    variety = dandelion["varieties"][0]

    assert dandelion["english_name"] == "Dandelion"
    assert dandelion["botanical_name"] == "Taraxacum officinale"
    assert variety["days_baby"] == 30
    assert variety["days_outer_leaf"] == 55
    assert manifest["plant_db_version"] == "2026.08.27.1"
    assert manifest["files"]["crops"]["sha256"] == hashlib.sha256(
        crops_path.read_bytes()
    ).hexdigest()
