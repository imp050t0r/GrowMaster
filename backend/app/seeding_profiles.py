from __future__ import annotations

import json
import os
from pathlib import Path


_TEMPLATE_FILE = Path(__file__).with_name("data") / "seeding_profiles.json"
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


def seeding_profile(crop_name: str, variety_name: str | None = None) -> dict:
    data = load_seeding_data()
    bed_width_cm = int(data.get("bed_width_cm", 80))
    defaults = data.get("defaults", {})
    profiles = data.get("profiles", {})

    profile = dict(profiles.get(crop_name, {}))
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
        "configured": bool(profile),
        "source": str(seeding_data_path()) if seeding_data_path().exists() else "bundled-template",
    }
