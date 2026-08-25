import hashlib
import json

import pytest

from app import plant_db_service


def encoded(payload: dict) -> bytes:
    return (json.dumps(payload) + "\n").encode()


def test_remote_update_verifies_and_atomically_installs_all_files(tmp_path, monkeypatch):
    monkeypatch.setenv("GROWMASTER_DATA_ROOT", str(tmp_path))
    manifest_url = "https://raw.githubusercontent.com/imp050t0r/GrowMaster/main/plant-db/latest/manifest.json"
    files = {
        "crops": encoded({"schema_version": 1, "crops": []}),
        "seeding": encoded({"schema_version": 1, "profiles": {}}),
        "rollers": encoded({"schema_version": 1, "roller_families": {}}),
        "rotation": encoded({"mixture_rotation_families": {}, "warm_season_crops": [], "winter_friendly_crops": [], "rotation": {}}),
    }
    names = {name: f"growmaster-{name}.json" for name in files}
    manifest = {
        "schema_version": 1, "plant_db_version": "2026.08.25.2",
        "minimum_app_version": "1.24.2",
        "files": {name: {"path": names[name], "sha256": hashlib.sha256(data).hexdigest()} for name, data in files.items()},
    }
    remote = {manifest_url: encoded(manifest)}
    remote.update({manifest_url.rsplit("/", 1)[0] + "/" + names[name]: data for name, data in files.items()})
    monkeypatch.setattr(plant_db_service, "_remote_bytes", remote.__getitem__)

    result = plant_db_service.install_remote_update()

    assert result["available_version"] == "2026.08.25.2"
    assert plant_db_service.status()["plant_db_version"] == "2026.08.25.2"
    assert json.loads(plant_db_service.master_data_path().read_text())["crops"] == []
    assert len(result["installed"]) == 4


def test_remote_update_rejects_a_bad_checksum(tmp_path, monkeypatch):
    monkeypatch.setenv("GROWMASTER_DATA_ROOT", str(tmp_path))
    manifest = {
        "schema_version": 1, "plant_db_version": "2026.08.25.2",
        "files": {name: {"path": f"{name}.json", "sha256": "0" * 64} for name in ("crops", "seeding", "rollers", "rotation")},
    }
    monkeypatch.setattr(plant_db_service, "_remote_bytes", lambda url: encoded(manifest) if url.endswith("manifest.json") else b"{}")

    with pytest.raises(ValueError, match="Kontrolna vsota"):
        plant_db_service.install_remote_update()
    assert not plant_db_service.manifest_path().exists()
