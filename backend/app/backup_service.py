from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

from app.plant_db_service import data_root


def backup_dir() -> Path:
    path = Path(os.getenv("BACKUP_DIR", str(data_root() / "backups")))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _db_env_and_args() -> tuple[dict, list[str]]:
    url = make_url(os.environ["DATABASE_URL"])
    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = url.password
    args = ["-h", url.host or "database", "-p", str(url.port or 5432), "-U", url.username or "growmaster", "-d", url.database or "growmaster"]
    return env, args


def list_backups() -> list[dict]:
    result = []
    for path in sorted(backup_dir().glob("GrowMaster-backup-*.zip"), reverse=True):
        stat = path.stat()
        result.append({"name": path.name, "size_bytes": stat.st_size, "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()})
    return result


def create_backup(label: str | None = None) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_label = "".join(ch for ch in (label or "") if ch.isalnum() or ch in "-_ ").strip().replace(" ", "-")[:40]
    name = f"GrowMaster-backup-{stamp}{'-' + safe_label if safe_label else ''}.zip"
    target = backup_dir() / name
    env, db_args = _db_env_and_args()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        dump = tmp / "database.dump"
        subprocess.run(["pg_dump", *db_args, "-Fc", "-f", str(dump)], env=env, check=True, capture_output=True)
        meta = {
            "format": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database": "PostgreSQL custom dump",
            "data_root": "/data",
        }
        (tmp / "backup.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(dump, "database.dump")
            archive.write(tmp / "backup.json", "backup.json")
            root = data_root()
            if root.exists():
                for path in root.rglob("*"):
                    if not path.is_file() or backup_dir() in path.parents:
                        continue
                    archive.write(path, Path("data") / path.relative_to(root))
    return next(item for item in list_backups() if item["name"] == name)


def restore_backup(name: str) -> dict:
    source = backup_dir() / Path(name).name
    if not source.exists() or source.parent != backup_dir():
        raise FileNotFoundError("Backup ne obstaja.")
    safety = create_backup("before-restore")
    env, db_args = _db_env_and_args()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with zipfile.ZipFile(source, "r") as archive:
            archive.extractall(tmp)
        dump = tmp / "database.dump"
        if not dump.exists():
            raise ValueError("Backup nima database.dump.")
        subprocess.run(["pg_restore", *db_args, "--clean", "--if-exists", "--no-owner", str(dump)], env=env, check=True, capture_output=True)
        restored_data = tmp / "data"
        if restored_data.exists():
            root = data_root()
            for path in restored_data.rglob("*"):
                if path.is_file():
                    dest = root / path.relative_to(restored_data)
                    if backup_dir() in dest.parents:
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, dest)
    return {"restored": source.name, "safety_backup": safety}
