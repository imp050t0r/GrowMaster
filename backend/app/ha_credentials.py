"""Encrypted, per-installation storage for the Home Assistant API credential."""
import json
import os
from pathlib import Path
import tempfile

from cryptography.fernet import Fernet, InvalidToken


def _paths() -> tuple[Path, Path]:
    root = Path(os.environ.get("GROWMASTER_DATA_ROOT", "/data"))
    directory = root / "secrets"
    return directory / "home-assistant.key", directory / "home-assistant.json"


def _fernet() -> Fernet:
    key_path, _ = _paths()
    key_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        key = key_path.read_bytes()
    else:
        key = Fernet.generate_key()
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(key)
            stream.flush()
            os.fsync(stream.fileno())
    try:
        os.chmod(key_path, 0o600)
        return Fernet(key)
    except (ValueError, OSError) as exc:
        raise RuntimeError("Ključa za šifriranje Home Assistanta ni mogoče prebrati.") from exc


def read_config() -> dict | None:
    _, config_path = _paths()
    if not config_path.exists():
        return None
    try:
        stored = json.loads(config_path.read_text(encoding="utf-8"))
        token = _fernet().decrypt(stored["token"].encode("ascii")).decode("utf-8")
        if not isinstance(stored.get("url"), str) or not token:
            raise ValueError("Neveljavna konfiguracija.")
        return {"url": stored["url"], "token": token}
    except (OSError, ValueError, KeyError, TypeError, InvalidToken, UnicodeError) as exc:
        raise RuntimeError("Shranjena povezava Home Assistanta je poškodovana; nastavi jo znova.") from exc


def write_config(url: str, token: str) -> None:
    key_path, config_path = _paths()
    config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = json.dumps({"url": url, "token": _fernet().encrypt(token.encode("utf-8")).decode("ascii")},
                         separators=(",", ":"))
    descriptor, temp_name = tempfile.mkstemp(prefix=".home-assistant-", dir=config_path.parent)
    try:
        os.chmod(temp_name, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, config_path)
        os.chmod(config_path, 0o600)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def delete_config() -> bool:
    _, config_path = _paths()
    try:
        config_path.unlink()
        return True
    except FileNotFoundError:
        return False
