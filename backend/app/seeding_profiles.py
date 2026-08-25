from __future__ import annotations

import json
import os
from pathlib import Path


_TEMPLATE_FILE = Path(__file__).with_name("data") / "seeding_profiles.json"
_ROLLER_FILE = Path(__file__).with_name("data") / "roller_catalog.json"
EXTERNAL_FILENAME = "growmaster-seeding.json"


def seeding_data_path() -> Path:
    configured = os.getenv("GROWMASTER_SEEDING_DATA_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    root = Path(os.getenv("GROWMASTER_DATA_ROOT", "/data"))
    return root / EXTERNAL_FILENAME


def _validate(payload: dict) -> dict:
    if payload.get("schema_version") != 1:
        raise ValueError("Nepodprta različica sejalniških profilov.")
    if not isinstance(payload.get("profiles"), dict):
        raise ValueError("Sejalniška datoteka nima veljavnih profilov.")
    return payload


def load_seeding_data() -> dict:
    external = seeding_data_path()
    source = external if external.exists() else _TEMPLATE_FILE
    return _validate(json.loads(source.read_text(encoding="utf-8")))


def load_roller_catalog() -> dict:
    return json.loads(_ROLLER_FILE.read_text(encoding="utf-8"))


def export_seeding_data() -> Path:
    path = seeding_data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        payload = _validate(json.loads(_TEMPLATE_FILE.read_text(encoding="utf-8")))
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return path


TRANSPLANT_FIRST = {
    "Paradižnik", "Paprika", "Feferon", "Jajčevec", "Indijski jajčevec",
    "Indijski čili", "Nepalski zeleni čili", "Zelena", "Por", "Zelje",
    "Cvetača", "Brokoli",
}

BRASSICA_DIRECT = {
    "Mizuna", "Pak Choi", "Tatsoi", "Komatsuna", "Choi Sum", "Kailan",
    "Daikon", "Pekinško zelje", "Mibuna", "Japonska repa", "Azijska gorčica",
    "Koleraba", "Repa",
}

LARGE_SEED_CALIBRATE = {
    "Fižol", "Grah", "Bob", "Edamame", "Bamija", "Karela", "Lauki",
    "Rebrasta bučka", "Gobasta bučka", "Tinda", "Voščena buča", "Kumara",
    "Bučka", "Buča", "Guar", "Methi",
}

SMALL_HERB = {"Peteršilj", "Shiso", "Koriander", "Koromač"}


def _fallback_profile(crop_name: str, crop_family: str | None, category: str | None) -> dict:
    if crop_name in TRANSPLANT_FIRST:
        return {
            "production_type": "transplant",
            "target_rows_per_80cm_bed": None,
            "seed_rate_g_m2": None,
            "jang_jp1": {
                "roller": None,
                "row_count": None,
                "calibration_required": False,
                "not_recommended": True,
                "note": "GrowMaster za to kulturo privzeto priporoča vzgojo sadik in presajanje, ne direktne setve z JP-1.",
            },
            "six_row": {"passes": None, "rows_per_bed": None},
            "note": "Profil je samodejno izpeljan iz načina pridelave; sortni podatki imajo prednost.",
        }
    if crop_name in BRASSICA_DIRECT or crop_family == "Brassicaceae":
        return {
            "production_type": "direct_sow",
            "target_rows_per_80cm_bed": 6,
            "seed_rate_g_m2": None,
            "jang_jp1": {
                "roller": "X24",
                "alternative_rollers": ["Y24", "F24"],
                "front_sprocket": 14,
                "rear_sprocket": 10,
                "brush": "low",
                "row_count": 6,
                "calibration_required": True,
                "confidence": "family-level",
                "note": "Brassicaceae imajo podobno območje velikosti semena, vendar se optimalen roller razlikuje po kulturi in sorti.",
            },
            "six_row": {"passes": 1, "rows_per_bed": 6},
        }
    if crop_name in {"Korenje"}:
        return {
            "production_type": "root",
            "target_rows_per_80cm_bed": 8,
            "seed_rate_g_m2": None,
            "jang_jp1": {"roller": "X24", "alternative_rollers": ["XY24", "LJ12"], "front_sprocket": 14, "rear_sprocket": 10, "brush": "low", "row_count": 8, "calibration_required": True},
            "six_row": {"passes": 2, "rows_per_bed": 12},
        }
    if crop_name in {"Rdeča pesa", "Blitva", "Mladi listi rdeče pese", "Baby leaf blitva"}:
        return {
            "production_type": "direct_sow",
            "target_rows_per_80cm_bed": 6,
            "seed_rate_g_m2": None,
            "jang_jp1": {"roller": "LJ12", "alternative_rollers": ["LJ6"], "front_sprocket": 14, "rear_sprocket": 10, "brush": "low", "row_count": 6, "calibration_required": True},
            "six_row": {"passes": 1, "rows_per_bed": 6},
        }
    if crop_name in {"Špinača"}:
        return {
            "production_type": "leaf",
            "target_rows_per_80cm_bed": 8,
            "seed_rate_g_m2": None,
            "jang_jp1": {"roller": "LJ24", "alternative_rollers": ["F24", "MJ24", "L24"], "front_sprocket": 14, "rear_sprocket": 9, "brush": "low", "row_count": 8, "calibration_required": True},
            "six_row": {"passes": 2, "rows_per_bed": 12},
        }
    if crop_name in SMALL_HERB:
        roller = "LJ12" if crop_name == "Koriander" else "MJ24"
        return {
            "production_type": "herb",
            "target_rows_per_80cm_bed": 6,
            "seed_rate_g_m2": None,
            "jang_jp1": {"roller": roller, "front_sprocket": 14, "rear_sprocket": 9, "brush": "low", "row_count": 6, "calibration_required": True},
            "six_row": {"passes": 1, "rows_per_bed": 6},
        }
    if crop_name in LARGE_SEED_CALIBRATE or crop_family in {"Cucurbitaceae", "Fabaceae", "Malvaceae"}:
        return {
            "production_type": "large_seed",
            "target_rows_per_80cm_bed": 2,
            "seed_rate_g_m2": None,
            "jang_jp1": {
                "roller": None,
                "alternative_roller_families": ["N", "Q", "R", "G", "C", "AA", "A"],
                "row_count": 2,
                "calibration_required": True,
                "confidence": "size-selection-required",
                "note": "Izberi roller po dejanski širini/debelini semena z Jang merilno mrežo; pri velikem semenu univerzalna nastavitev ni varna.",
            },
            "six_row": {"passes": None, "rows_per_bed": None, "not_recommended": True},
        }
    if category == "Baby leaf":
        return {
            "production_type": "baby_leaf",
            "target_rows_per_80cm_bed": 12,
            "seed_rate_g_m2": None,
            "jang_jp1": {"roller": None, "alternative_roller_families": ["Y", "X", "F", "XY", "YYX"], "front_sprocket": 14, "rear_sprocket": 9, "brush": "low", "row_count": 12, "calibration_required": True},
            "six_row": {"passes": 2, "rows_per_bed": 12},
        }
    return {
        "production_type": "direct_sow_or_transplant",
        "target_rows_per_80cm_bed": None,
        "seed_rate_g_m2": None,
        "jang_jp1": {"roller": None, "calibration_required": True, "note": "Ni dovolj zanesljive univerzalne roller nastavitve; uporabi velikost semena in roller katalog."},
        "six_row": {"passes": None, "rows_per_bed": None},
    }


def seeding_profile(
    crop_name: str,
    variety_name: str | None = None,
    crop_family: str | None = None,
    category: str | None = None,
) -> dict:
    data = load_seeding_data()
    bed_width_cm = int(data.get("bed_width_cm", 80))
    defaults = data.get("defaults", {})
    profiles = data.get("profiles", {})

    explicit = crop_name in profiles
    profile = dict(profiles.get(crop_name, {})) if explicit else _fallback_profile(crop_name, crop_family, category)
    variety_overrides = profile.pop("varieties", {}) if profile else {}
    if variety_name and variety_name in variety_overrides:
        profile.update(variety_overrides[variety_name])

    jang = dict(defaults.get("jang_jp1", {}))
    jang.update(profile.get("jang_jp1", {}))
    six_row = dict(defaults.get("six_row", {}))
    six_row.update(profile.get("six_row", {}))

    return {
        "bed_width_cm": bed_width_cm,
        "production_type": profile.get("production_type"),
        "target_rows_per_bed": profile.get("target_rows_per_80cm_bed"),
        "seed_rate_g_m2": profile.get("seed_rate_g_m2"),
        "jang_jp1": jang,
        "six_row": six_row,
        "note": profile.get("note"),
        "configured": True,
        "explicit_profile": explicit,
        "profile_basis": "crop/variety" if explicit else "crop-family/production-type fallback",
        "roller_catalog_available": True,
        "source": str(seeding_data_path()) if seeding_data_path().exists() else "bundled-template",
    }
