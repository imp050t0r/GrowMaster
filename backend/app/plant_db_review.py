from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.plant_db_service import data_root

REVIEW_FILENAME = "growmaster-plant-db-review.json"
REVIEW_SCHEMA_VERSION = 1


def review_path() -> Path:
    return data_root() / REVIEW_FILENAME


def read_review_state() -> dict:
    path = review_path()
    if not path.exists():
        return {"schema_version": REVIEW_SCHEMA_VERSION, "last_reviewed_version": None, "entries": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != REVIEW_SCHEMA_VERSION:
        raise ValueError("Nepodprta shema Plant DB review stanja.")
    if not isinstance(payload.get("entries"), dict):
        payload["entries"] = {}
    return payload


def write_review_state(payload: dict) -> None:
    path = review_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def classify_entries(entries: list[dict], include_skipped: bool = False) -> tuple[list[dict], list[dict]]:
    state = read_review_state()
    known = state.get("entries", {})
    fresh: list[dict] = []
    skipped: list[dict] = []
    for entry in entries:
        record = known.get(entry["key"])
        if not record:
            fresh.append(entry)
        elif record.get("status") == "skipped":
            skipped.append(entry)
    return fresh, skipped if include_skipped else []


def mark_review(version: str, shown_keys: set[str], approved_keys: set[str]) -> dict:
    state = read_review_state()
    records = state.setdefault("entries", {})
    now = datetime.now(timezone.utc).isoformat()
    for key in shown_keys:
        records[key] = {
            "status": "approved" if key in approved_keys else "skipped",
            "reviewed_version": version,
            "reviewed_at": now,
        }
    state["last_reviewed_version"] = version
    state["last_reviewed_at"] = now
    write_review_state(state)
    return state


def review_summary() -> dict:
    state = read_review_state()
    records = state.get("entries", {})
    return {
        "last_reviewed_version": state.get("last_reviewed_version"),
        "approved_count": sum(1 for item in records.values() if item.get("status") == "approved"),
        "skipped_count": sum(1 for item in records.values() if item.get("status") == "skipped"),
    }
