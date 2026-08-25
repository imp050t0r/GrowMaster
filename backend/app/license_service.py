from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


LICENSE_SCHEMA_VERSION = 1
TRIAL_DAYS = int(os.getenv("GROWMASTER_TRIAL_DAYS", "30"))
PUBLIC_KEY_B64 = os.getenv(
    "GROWMASTER_LICENSE_PUBLIC_KEY",
    "ZMSn4A2cHd+f8LTiD+oxoFpDbtemjr0nm0tTCWegy60=",
)
STATE_FILENAME = "growmaster-license-state.json"
LICENSE_FILENAME = "growmaster-license.json"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _data_root() -> Path:
    return Path(os.getenv("GROWMASTER_DATA_ROOT", "/data"))


def state_path() -> Path:
    return _data_root() / STATE_FILENAME


def license_path() -> Path:
    configured = os.getenv("GROWMASTER_LICENSE_FILE")
    return Path(configured).expanduser().resolve() if configured else _data_root() / LICENSE_FILENAME


def _machine_hint() -> str:
    parts = [platform.system(), platform.machine(), platform.node()]
    for candidate in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            if candidate.exists():
                parts.append(candidate.read_text(encoding="utf-8").strip())
                break
        except OSError:
            pass
    parts.append(str(uuid.getnode()))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_or_create_state() -> dict:
    path = state_path()
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") == LICENSE_SCHEMA_VERSION:
            return payload
    payload = {
        "schema_version": LICENSE_SCHEMA_VERSION,
        "installation_id": str(uuid.uuid4()),
        "device_fingerprint": _machine_hint(),
        "trial_started_at": _utcnow().isoformat(),
    }
    _write_json(path, payload)
    return payload


def activation_request_code() -> str:
    state = load_or_create_state()
    raw = f"{state['installation_id']}|{state['device_fingerprint']}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()
    return f"GM-{state['installation_id'][:8].upper()}-{digest}"


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def verify_license_token(token: str, public_key_b64: str | None = None) -> dict:
    try:
        payload_part, signature_part = token.strip().split(".", 1)
        payload_bytes = _b64url_decode(payload_part)
        signature = _b64url_decode(signature_part)
        key_raw = base64.b64decode(public_key_b64 or PUBLIC_KEY_B64)
        Ed25519PublicKey.from_public_bytes(key_raw).verify(signature, payload_bytes)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError, InvalidSignature) as exc:
        raise ValueError("Licenčni podpis ni veljaven.") from exc
    if payload.get("schema_version") != LICENSE_SCHEMA_VERSION:
        raise ValueError("Licenca uporablja nepodprto shemo.")
    if payload.get("edition") not in {"pro", "admin"}:
        raise ValueError("Licenca nima veljavne izdaje.")
    if not payload.get("license_id"):
        raise ValueError("Licenca nima identifikatorja.")
    return payload


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def validate_for_this_install(payload: dict) -> None:
    state = load_or_create_state()
    device_id = payload.get("device_id")
    if device_id and device_id not in {state["installation_id"], activation_request_code()}:
        raise ValueError("Licenca je izdana za drugo namestitev GrowMasterja.")
    not_before = _parse_time(payload.get("not_before"))
    expires_at = _parse_time(payload.get("expires_at"))
    now = _utcnow()
    if not_before and now < not_before:
        raise ValueError("Licenca še ni veljavna.")
    if expires_at and now > expires_at:
        raise ValueError("Licenca je potekla.")


def activate(token: str) -> dict:
    payload = verify_license_token(token)
    validate_for_this_install(payload)
    _write_json(
        license_path(),
        {
            "schema_version": LICENSE_SCHEMA_VERSION,
            "activated_at": _utcnow().isoformat(),
            "token": token.strip(),
        },
    )
    return status()


def _licensed_payload() -> tuple[dict | None, str | None]:
    path = license_path()
    if not path.exists():
        return None, None
    try:
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        payload = verify_license_token(wrapper.get("token", ""))
        validate_for_this_install(payload)
        return payload, None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)


def status() -> dict:
    state = load_or_create_state()
    licensed, license_error = _licensed_payload()
    if licensed:
        return {
            "mode": licensed["edition"],
            "edition": licensed["edition"],
            "full_access": True,
            "admin_access": licensed["edition"] == "admin",
            "customer": licensed.get("customer"),
            "license_id": licensed.get("license_id"),
            "expires_at": licensed.get("expires_at"),
            "installation_id": state["installation_id"],
            "activation_request_code": activation_request_code(),
            "trial_days": TRIAL_DAYS,
            "trial_days_left": 0,
            "license_error": None,
        }

    started = _parse_time(state.get("trial_started_at")) or _utcnow()
    trial_end = started + timedelta(days=TRIAL_DAYS)
    now = _utcnow()
    remaining_seconds = max(0.0, (trial_end - now).total_seconds())
    days_left = int((remaining_seconds + 86399) // 86400)
    active = now <= trial_end
    return {
        "mode": "trial" if active else "trial_expired",
        "edition": "trial",
        "full_access": active,
        "admin_access": False,
        "customer": None,
        "license_id": None,
        "expires_at": trial_end.isoformat(),
        "installation_id": state["installation_id"],
        "activation_request_code": activation_request_code(),
        "trial_days": TRIAL_DAYS,
        "trial_days_left": days_left,
        "license_error": license_error,
    }


def require_full_access() -> None:
    if not status()["full_access"]:
        raise PermissionError("Testno obdobje je poteklo. Aktiviraj GrowMaster Pro.")


def require_admin_access() -> None:
    if not status()["admin_access"]:
        raise PermissionError("Ta funkcija zahteva GrowMaster Admin licenco.")
