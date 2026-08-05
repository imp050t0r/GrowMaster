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

        harvest = client.post(
            "/api/harvests",
            json={
                "planting_id": planting.json()["id"],
                "harvest_date": "2026-09-10",
                "quantity_kg": 18.5,
                "quality": "A",
                "notes": "Prva kakovost.",
            },
        )
        assert harvest.status_code == 201
        assert harvest.json()["available_kg"] == 18.5

        cost = client.post(
            "/api/costs",
            json={
                "bed_id": bed["id"],
                "planting_id": planting.json()["id"],
                "cost_date": "2026-09-09",
                "category": "labor",
                "amount_eur": 42.5,
                "description": "Pobiranje in pakiranje",
            },
        )
        assert cost.status_code == 201

        sale = client.post(
            "/api/sales",
            json={
                "harvest_id": harvest.json()["id"],
                "sale_date": "2026-09-10",
                "quantity_kg": 15,
                "price_per_kg_eur": 6,
                "customer": "Tržnica",
            },
        )
        assert sale.status_code == 201
        assert sale.json()["revenue_eur"] == 90

        oversold = client.post(
            "/api/sales",
            json={
                "harvest_id": harvest.json()["id"],
                "sale_date": "2026-09-10",
                "quantity_kg": 4,
                "price_per_kg_eur": 6,
            },
        )
        assert oversold.status_code == 409

        harvest_summary = client.get("/api/harvests").json()[0]
        assert harvest_summary["sold_kg"] == 15
        assert harvest_summary["available_kg"] == 3.5

        economics = client.get("/api/economics/by-bed").json()
        bed_economics = next(item for item in economics if item["bed_id"] == bed["id"])
        assert bed_economics["harvested_kg"] == 18.5
        assert bed_economics["costs_eur"] == 42.5
        assert bed_economics["revenue_eur"] == 90
        assert bed_economics["profit_eur"] == 47.5
