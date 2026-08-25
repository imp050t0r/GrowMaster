from __future__ import annotations

import json
import os
import shutil
from datetime import date
from pathlib import Path

from app.master_data_service import master_data_path
from app.seeding_profiles import seeding_data_path


PLANT_DB_MANIFEST = "growmaster-plant-db.json"
ROLLER_FILENAME = "growmaster-rollers.json"
ROTATION_FILENAME = "growmaster-rotation.json"
PLANT_DB_SCHEMA_VERSION = 1


def data_root() -> Path:
    return Path(os.getenv("GROWMASTER_DATA_ROOT", "/data"))


def manifest_path() -> Path:
    return data_root() / PLANT_DB_MANIFEST


def roller_data_path() -> Path:
    configured = os.getenv("GROWMASTER_ROLLER_DATA_FILE")
    return Path(configured).expanduser().resolve() if configured else data_root() / ROLLER_FILENAME


def rotation_data_path() -> Path:
    configured = os.getenv("GROWMASTER_ROTATION_DATA_FILE")
    return Path(configured).expanduser().resolve() if configured else data_root() / ROTATION_FILENAME


def _template(name: str) -> Path:
    return Path(__file__).with_name("data") / name


def ensure_external_files() -> dict:
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    copies = [
        (roller_data_path(), _template("roller_catalog.json")),
        (rotation_data_path(), _template("rotation_rules.json")),
        (seeding_data_path(), _template("seeding_profiles.json")),
    ]
    created = []
    for target, source in copies:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            created.append(str(target))
    if not manifest_path().exists():
        payload = {
            "schema_version": PLANT_DB_SCHEMA_VERSION,
            "plant_db_version": date.today().isoformat() + ".1",
            "files": {
                "crops": str(master_data_path()),
                "seeding": str(seeding_data_path()),
                "rollers": str(roller_data_path()),
                "rotation": str(rotation_data_path()),
            },
        }
        manifest_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created.append(str(manifest_path()))
    return {"created": created, **status()}


def read_manifest() -> dict:
    if not manifest_path().exists():
        ensure_external_files()
    payload = json.loads(manifest_path().read_text(encoding="utf-8"))
    if payload.get("schema_version") != PLANT_DB_SCHEMA_VERSION:
        raise ValueError("Nepodprta shema Plant DB.")
    return payload


def status() -> dict:
    version = None
    if manifest_path().exists():
        try:
            version = json.loads(manifest_path().read_text(encoding="utf-8")).get("plant_db_version")
        except Exception:
            version = None
    files = {
        "crops": master_data_path(),
        "seeding": seeding_data_path(),
        "rollers": roller_data_path(),
        "rotation": rotation_data_path(),
    }
    return {
        "plant_db_version": version,
        "schema_version": PLANT_DB_SCHEMA_VERSION,
        "manifest": str(manifest_path()),
        "files": {name: {"path": str(path), "exists": path.exists()} for name, path in files.items()},
        "independent_from_app_release": True,
    }


def load_roller_catalog() -> dict:
    path = roller_data_path()
    source = path if path.exists() else _template("roller_catalog.json")
    return json.loads(source.read_text(encoding="utf-8"))


def load_rotation_rules() -> dict:
    path = rotation_data_path()
    source = path if path.exists() else _template("rotation_rules.json")
    return json.loads(source.read_text(encoding="utf-8"))
