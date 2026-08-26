from __future__ import annotations

import json
import hashlib
import os
import shutil
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from app.master_data_service import master_data_path
from app.seeding_profiles import seeding_data_path


PLANT_DB_MANIFEST = "growmaster-plant-db.json"
ROLLER_FILENAME = "growmaster-rollers.json"
ROTATION_FILENAME = "growmaster-rotation.json"
PLANT_DB_SCHEMA_VERSION = 1
PLANT_DB_APP_VERSION = "1.24.3"
DEFAULT_REMOTE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/imp050t0r/GrowMaster/main/"
    "plant-db/latest/manifest.json"
)
MAX_REMOTE_FILE_BYTES = 20 * 1024 * 1024


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
        "remote_manifest_url": remote_manifest_url(),
    }


def remote_manifest_url() -> str:
    return os.getenv("GROWMASTER_PLANT_DB_MANIFEST_URL", DEFAULT_REMOTE_MANIFEST_URL)


def _allowed_hosts() -> set[str]:
    configured = os.getenv("GROWMASTER_PLANT_DB_ALLOWED_HOSTS", "raw.githubusercontent.com")
    return {host.strip().lower() for host in configured.split(",") if host.strip()}


def _remote_bytes(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in _allowed_hosts():
        raise ValueError("Plant DB URL ni na dovoljenem HTTPS gostitelju.")
    request = Request(url, headers={"User-Agent": "GrowMaster-PlantDB/1"})
    with urlopen(request, timeout=20) as response:
        content_length = int(response.headers.get("Content-Length") or 0)
        if content_length > MAX_REMOTE_FILE_BYTES:
            raise ValueError("Oddaljena Plant DB datoteka je prevelika.")
        payload = response.read(MAX_REMOTE_FILE_BYTES + 1)
    if len(payload) > MAX_REMOTE_FILE_BYTES:
        raise ValueError("Oddaljena Plant DB datoteka je prevelika.")
    return payload


def fetch_remote_manifest() -> dict:
    payload = json.loads(_remote_bytes(remote_manifest_url()).decode("utf-8"))
    if payload.get("schema_version") != PLANT_DB_SCHEMA_VERSION:
        raise ValueError("Oddaljeni manifest uporablja nepodprto shemo.")
    if not payload.get("plant_db_version") or not isinstance(payload.get("files"), dict):
        raise ValueError("Oddaljeni manifest ni popoln.")
    return payload


def _version_key(value: str | None) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(value or "0").replace("-", ".").split(".") if part.isdigit())
    except ValueError:
        return (0,)


def remote_update_status() -> dict:
    remote = fetch_remote_manifest()
    local = status().get("plant_db_version")
    return {
        "current_version": local,
        "available_version": remote["plant_db_version"],
        "update_available": _version_key(remote["plant_db_version"]) > _version_key(local),
        "minimum_app_version": remote.get("minimum_app_version"),
    }


def install_remote_update() -> dict:
    manifest_url = remote_manifest_url()
    manifest = fetch_remote_manifest()
    minimum_app_version = manifest.get("minimum_app_version")
    if minimum_app_version and _version_key(minimum_app_version) > _version_key(PLANT_DB_APP_VERSION):
        raise ValueError(
            f"Plant DB zahteva GrowMaster {minimum_app_version} ali novejši."
        )
    targets = {
        "crops": master_data_path(),
        "seeding": seeding_data_path(),
        "rollers": roller_data_path(),
        "rotation": rotation_data_path(),
    }
    staged: dict[str, bytes] = {}
    for name, target in targets.items():
        descriptor = manifest["files"].get(name)
        if not isinstance(descriptor, dict) or not descriptor.get("path") or not descriptor.get("sha256"):
            raise ValueError(f"Manifest nima veljavnega zapisa za {name}.")
        data = _remote_bytes(urljoin(manifest_url, descriptor["path"]))
        if hashlib.sha256(data).hexdigest() != descriptor["sha256"]:
            raise ValueError(f"Kontrolna vsota Plant DB datoteke {name} se ne ujema.")
        json.loads(data.decode("utf-8"))
        staged[name] = data

    backup_root = data_root() / "plant-db-backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root.mkdir(parents=True, exist_ok=True)
    installed = []
    for name, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.copy2(target, backup_root / target.name)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            handle.write(staged[name])
            temporary = Path(handle.name)
        temporary.replace(target)
        installed.append(str(target))

    manifest_payload = {
        "schema_version": PLANT_DB_SCHEMA_VERSION,
        "plant_db_version": manifest["plant_db_version"],
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "source": manifest_url,
        "files": {name: str(path) for name, path in targets.items()},
    }
    _manifest_tmp = manifest_path().with_suffix(".json.tmp")
    _manifest_tmp.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _manifest_tmp.replace(manifest_path())
    return {"installed": installed, "backup": str(backup_root), **remote_update_status()}


def load_roller_catalog() -> dict:
    path = roller_data_path()
    source = path if path.exists() else _template("roller_catalog.json")
    return json.loads(source.read_text(encoding="utf-8"))


def load_rotation_rules() -> dict:
    path = rotation_data_path()
    source = path if path.exists() else _template("rotation_rules.json")
    return json.loads(source.read_text(encoding="utf-8"))
