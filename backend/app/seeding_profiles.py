from __future__ import annotations

import json
from pathlib import Path


_DATA_FILE = Path(__file__).with_name("data") / "seeding_profiles.json"


def _load() -> dict:
    with _DATA_FILE.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema_version") != 1:
        raise ValueError("Nepodprta različica sejalniških profilov.")
    return payload


_DATA = _load()
BED_WIDTH_CM = int(_DATA.get("bed_width_cm", 80))
DEFAULTS = _DATA.get("defaults", {})
PROFILES = _DATA.get("profiles", {})


def seeding_profile(crop_name: str, variety_name: str | None = None) -> dict:
    profile = dict(PROFILES.get(crop_name, {}))
    variety_overrides = profile.pop("varieties", {}) if profile else {}
    if variety_name and variety_name in variety_overrides:
        profile.update(variety_overrides[variety_name])

    jang = dict(DEFAULTS.get("jang_jp1", {}))
    jang.update(profile.get("jang_jp1", {}))
    six_row = dict(DEFAULTS.get("six_row", {}))
    six_row.update(profile.get("six_row", {}))

    return {
        "bed_width_cm": BED_WIDTH_CM,
        "production_type": profile.get("production_type"),
        "target_rows_per_bed": profile.get("target_rows_per_80cm_bed"),
        "seed_rate_g_m2": profile.get("seed_rate_g_m2"),
        "jang_jp1": jang,
        "six_row": six_row,
        "note": profile.get("note"),
        "configured": bool(profile),
    }
