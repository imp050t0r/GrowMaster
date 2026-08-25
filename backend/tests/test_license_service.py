from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from app import license_service


def _token(private_key: Ed25519PrivateKey, payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    b64 = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    return f"{b64(raw)}.{b64(private_key.sign(raw))}"


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("GROWMASTER_DATA_ROOT", str(tmp_path))
    private = Ed25519PrivateKey.generate()
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    monkeypatch.setattr(license_service, "PUBLIC_KEY_B64", base64.b64encode(public_raw).decode())
    return private


def test_trial_starts_with_full_access(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    current = license_service.status()
    assert current["mode"] == "trial"
    assert current["full_access"] is True
    assert current["trial_days_left"] == license_service.TRIAL_DAYS


def test_signed_pro_license_activates_for_installation(tmp_path, monkeypatch):
    private = _setup(tmp_path, monkeypatch)
    state = license_service.load_or_create_state()
    payload = {
        "schema_version": 1,
        "license_id": "GM-TEST-PRO",
        "edition": "pro",
        "customer": "Test Farm",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "device_id": state["installation_id"],
        "expires_at": None,
    }
    current = license_service.activate(_token(private, payload))
    assert current["mode"] == "pro"
    assert current["full_access"] is True
    assert current["admin_access"] is False


def test_admin_license_enables_admin_access(tmp_path, monkeypatch):
    private = _setup(tmp_path, monkeypatch)
    payload = {
        "schema_version": 1,
        "license_id": "GM-TEST-ADMIN",
        "edition": "admin",
        "customer": "Owner",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "device_id": license_service.activation_request_code(),
        "expires_at": None,
    }
    current = license_service.activate(_token(private, payload))
    assert current["mode"] == "admin"
    assert current["admin_access"] is True


def test_license_for_other_device_is_rejected(tmp_path, monkeypatch):
    private = _setup(tmp_path, monkeypatch)
    payload = {
        "schema_version": 1,
        "license_id": "GM-WRONG-DEVICE",
        "edition": "pro",
        "customer": "Other",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "device_id": "GM-OTHER-DEVICE",
        "expires_at": None,
    }
    with pytest.raises(ValueError, match="drugo namestitev"):
        license_service.activate(_token(private, payload))


def test_expired_license_is_rejected(tmp_path, monkeypatch):
    private = _setup(tmp_path, monkeypatch)
    payload = {
        "schema_version": 1,
        "license_id": "GM-EXPIRED",
        "edition": "pro",
        "customer": "Expired",
        "issued_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        "device_id": license_service.load_or_create_state()["installation_id"],
        "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    }
    with pytest.raises(ValueError, match="potekla"):
        license_service.activate(_token(private, payload))
