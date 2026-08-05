import os
from pathlib import Path

TEST_DATABASE = Path("growmaster-test.db")
TEST_DATABASE.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DATABASE}"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_bed_planting_and_task_workflow() -> None:
    with TestClient(app) as client:
        beds = client.get("/api/beds").json()
        crops = client.get("/api/crops").json()
        assert len(beds) == 6
        assert crops

        new_bed = client.post(
            "/api/beds",
            json={"name": "B1", "width_m": 0.8, "length_m": 15},
        )
        assert new_bed.status_code == 201
        assert new_bed.json()["area_m2"] == 12.0

        crop = next(item for item in crops if item["name"] == "Rukola")
        variety = next(item for item in crop["varieties"] if item["name"] == "Astro")
        bed = next(item for item in beds if item["name"] == "A3")
        planting = client.post(
            "/api/plantings",
            json={
                "crop_id": crop["id"],
                "variety_id": variety["id"],
                "bed_id": bed["id"],
                "sowing_date": "2026-08-05",
            },
        )
        assert planting.status_code == 201
        assert "tri opravila" in planting.json()["message"]

        detail = client.get(f"/api/beds/{bed['id']}")
        assert detail.status_code == 200
        assert detail.json()["current_planting"]["variety"] == "Astro"
        planting_tasks = [
            item
            for item in detail.json()["tasks"]
            if item["planting_id"] == planting.json()["id"]
        ]
        assert len(planting_tasks) == 3

        task = planting_tasks[0]
        completed = client.post(
            f"/api/tasks/{task['id']}/complete",
            json={
                "duration_minutes": 25,
                "quantity_used": 120,
                "unit": "L",
                "notes": "Pregled in zalivanje zaključena.",
            },
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert completed.json()["duration_minutes"] == 25

        finished = client.post(f"/api/plantings/{planting.json()['id']}/finish")
        assert finished.status_code == 200
        refreshed_bed = client.get(f"/api/beds/{bed['id']}").json()
        assert refreshed_bed["status"] == "empty"
        assert refreshed_bed["last_crop_family"] == "Brassicaceae"
