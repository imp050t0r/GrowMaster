import hashlib
import json
from pathlib import Path

from app.eu_chard_crops import EU_CHARD_CROPS
from app.eu_leafy_crops import EU_LEAFY_CROPS
from app.mix_recipes import BABY_LEAF_MIX_RECIPES, validate_mix_recipe
from app.professional_completion_catalog import PROFESSIONAL_COMPLETION_CATALOG
from app.south_asian_chilies import SOUTH_ASIAN_CHILIES
from app.south_asian_requested_crops import SOUTH_ASIAN_REQUESTED_CROPS


ROOT = Path(__file__).resolve().parents[2]


def test_completion_catalog_entries_are_traceable_professional_profiles():
    assert len(PROFESSIONAL_COMPLETION_CATALOG) >= 35
    for item in PROFESSIONAL_COMPLETION_CATALOG:
        assert item["crop"]
        assert item["name"]
        assert item["source_name"]
        assert item["source_url"].startswith("https://")
        assert item["traits"]
        assert item["slovenia_note"]


def test_indian_professional_batch_has_official_iihr_sources():
    expected = {
        ("Bamija", "Arka Abhay"),
        ("Palak", "Arka Anupama"),
        ("Kumara", "Arka Veera"),
        ("Lauki", "Arka Ganga F1"),
        ("Rebrasta bučka", "Arka Vikram F1"),
        ("Indijski jajčevec", "Arka Anand F1"),
        ("Listni amarant", "Arka Arunima"),
        ("Koriander", "Arka Isha"),
        ("Indijski čili", "Arka Harita F1"),
    }
    catalog = SOUTH_ASIAN_REQUESTED_CROPS + SOUTH_ASIAN_CHILIES
    found = {(item["crop"], item["name"]) for item in catalog}

    assert expected <= found
    for item in catalog:
        if (item["crop"], item["name"]) not in expected:
            continue
        assert item["source_name"].startswith("ICAR-IIHR")
        assert item["source_url"].startswith("https://nhfqr.iihr.res.in/")
        assert "profesionalno" in item["seed_forms"]


def test_bitter_gourd_has_verified_professional_indian_varieties():
    karela = {
        item["name"]: item
        for item in SOUTH_ASIAN_REQUESTED_CROPS
        if item["crop"] == "Karela"
    }
    expected = {
        "Small Indian",
        "Large Indian",
        "Pusa Aushadhi",
        "Pusa Rasdar",
        "Pusa Purvi",
        "Kashi Pratishtha",
        "Arka Harit",
    }

    assert expected <= karela.keys()
    for name in expected - {"Small Indian", "Large Indian"}:
        assert karela[name]["source_name"].startswith("ICAR-")
        assert karela[name]["source_url"].startswith("https://")
        assert "profesionalno" in karela[name]["seed_forms"]
        assert karela[name]["harvest_methods"] == "green_fruit"


def test_remaining_indian_gourds_have_verified_professional_varieties():
    expected = {
        ("Lauki", "Arka Shreyas"),
        ("Rebrasta bučka", "Arka Prasan"),
        ("Rebrasta bučka", "Kashi Nanda"),
        ("Rebrasta bučka", "Kashi Shivani"),
        ("Gobasta bučka", "Kashi Divya"),
        ("Gobasta bučka", "Kashi Vandana"),
        ("Gobasta bučka", "Kashi Rakshita F1"),
        ("Tinda", "Punjab Tinda-1"),
        ("Voščena buča", "TNAU Ash Gourd Hybrid CO 1 F1"),
        ("Voščena buča", "CO 2"),
    }
    catalog = {
        (item["crop"], item["name"]): item
        for item in SOUTH_ASIAN_REQUESTED_CROPS
    }

    assert expected <= catalog.keys()
    for key in expected:
        item = catalog[key]
        assert item["source_url"].startswith("https://")
        assert "profesionalno" in item["seed_forms"]
        assert item["planting_method"] == "transplant"
        assert item["harvest_methods"] in {"green_fruit", "full_size"}


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

    names = {item["name"] for item in EU_LEAFY_CROPS if item["crop"] == "Regrat"}
    assert {"Navadni regrat", "Vert de Montmagny", "A Coeur Plein Amélioré", "Nouvelle"} <= names


def test_chard_has_standard_and_baby_leaf_varieties():
    standard = {item["name"] for item in EU_CHARD_CROPS if item["crop"] == "Blitva"}
    baby = {item["name"] for item in EU_CHARD_CROPS if item["crop"] == "Baby leaf blitva"}

    assert {"Verte à Carde Blanche 3 Race B", "Jessica", "Bright Lights", "Bright Yellow", "Rhubarb Chard Rubis", "Galaxy F1"} <= standard
    assert {"Verte à Couper (Bette à Tondre)", "Barby", "Rhubarb Chard Rubis"} <= baby


def test_mix_recipes_are_structured_and_sum_to_100_percent():
    assert BABY_LEAF_MIX_RECIPES
    for recipe in BABY_LEAF_MIX_RECIPES:
        assert validate_mix_recipe(recipe)
        assert recipe["strategy"] == "separate_then_mix"
        assert sum(component["share_pct"] for component in recipe["components"]) == 100


def test_public_plant_db_release_contains_dandelion_chard_and_matches_manifest():
    release = ROOT / "plant-db" / "latest"
    crops_path = release / "growmaster-crops.json"
    payload = json.loads(crops_path.read_text(encoding="utf-8"))
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))

    dandelion = next(crop for crop in payload["crops"] if crop["name"] == "Regrat")
    baby_dandelion = next(crop for crop in payload["crops"] if crop["name"] == "Baby leaf regrat")
    chard = next(crop for crop in payload["crops"] if crop["name"] == "Blitva")
    baby_chard = next(crop for crop in payload["crops"] if crop["name"] == "Baby leaf blitva")

    assert dandelion["english_name"] == "Dandelion"
    assert dandelion["botanical_name"] == "Taraxacum officinale"
    assert baby_dandelion["varieties"]
    assert len(chard["varieties"]) >= 6
    assert len(baby_chard["varieties"]) >= 3
    assert manifest["plant_db_version"] == "2026.08.27.3"
    assert manifest["files"]["crops"]["sha256"] == hashlib.sha256(
        crops_path.read_bytes()
    ).hexdigest()
