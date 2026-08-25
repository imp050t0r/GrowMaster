from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

TEST_DATABASE = Path("growmaster-test.db")
TEST_DATABASE.unlink(missing_ok=True)
TEST_BACKUP_DIRECTORY = Path("tmp/growmaster-test-backups")
shutil.rmtree(TEST_BACKUP_DIRECTORY, ignore_errors=True)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DATABASE}"
os.environ["BACKUP_DIR"] = str(TEST_BACKUP_DIRECTORY)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.backups import (  # noqa: E402
    canonical_json,
    ensure_daily_backup,
    list_daily_backups,
    parse_backup,
    refresh_daily_backup,
)
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app, demo_data_available, prepare_farm_on_first_setup  # noqa: E402
from app.migrations import run_migrations, schema_migrations  # noqa: E402
from app.models import Bed, Crop, Planting, Task, Variety  # noqa: E402
from app.seed import seed_database  # noqa: E402


def test_bed_planting_and_task_workflow() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json() == {
            "app": "GrowMaster",
            "status": "running",
            "version": "1.22.1",
        }
        with SessionLocal() as db:
            assert demo_data_available(db) is True
            assert prepare_farm_on_first_setup(
                db, "Prazna testna kmetija", keep_demo_data=False
            ) is True
            assert db.scalar(select(func.count()).select_from(Bed)) == 0
            assert db.scalar(select(func.count()).select_from(Task)) == 0
            db.rollback()
        with SessionLocal() as db:
            first_bed = db.scalar(select(Bed).where(Bed.name == "A1"))
            first_bed.length_m = 16
            db.flush()
            assert demo_data_available(db) is False
            db.rollback()

        auth_status = client.get("/api/auth/status")
        assert auth_status.status_code == 200
        assert auth_status.json() == {
            "configured": False,
            "authenticated": False,
            "display_name": None,
            "session_days": 30,
            "demo_data_available": True,
        }
        protected = client.get(
            "/api/beds", headers={"Origin": "http://localhost:3000"}
        )
        assert protected.status_code == 401
        assert client.get("/api/system/readiness").status_code == 401
        assert protected.headers["access-control-allow-origin"] == (
            "http://localhost:3000"
        )
        assert client.post(
            "/api/auth/setup",
            json={
                "display_name": "Nosilec kmetije",
                "farm_name": "Testna kmetija",
                "password": "prekratko",
            },
        ).status_code == 422
        assert client.post(
            "/api/auth/setup",
            json={
                "display_name": "   ",
                "farm_name": "Testna kmetija",
                "password": "Zelo varno geslo 2026!",
            },
        ).status_code == 422
        setup = client.post(
            "/api/auth/setup",
            json={
                "display_name": "Nosilec kmetije",
                "farm_name": "Testna kmetija",
                "keep_demo_data": True,
                "password": "Zelo varno geslo 2026!",
            },
        )
        assert setup.status_code == 201
        assert setup.json()["authenticated"] is True
        assert setup.json()["display_name"] == "Nosilec kmetije"
        set_cookie = setup.headers["set-cookie"].lower()
        assert "growmaster_session=" in set_cookie
        assert "httponly" in set_cookie
        assert "samesite=strict" in set_cookie
        assert client.post(
            "/api/auth/setup",
            json={
                "display_name": "Drugi uporabnik",
                "farm_name": "Druga kmetija",
                "password": "Drugo varno geslo 2026!",
            },
        ).status_code == 409

        assert run_migrations() == "0008_green_chilli_harvest"
        assert run_migrations() == "0008_green_chilli_harvest"
        with engine.connect() as connection:
            assert connection.scalar(
                select(func.count()).select_from(schema_migrations)
            ) == 8
        initial_profile = client.get("/api/farm-profile")
        assert initial_profile.status_code == 200
        assert initial_profile.json()["farm_name"] == "Testna kmetija"
        assert initial_profile.json()["business_documents_ready"] is False
        initial_readiness = client.get("/api/system/readiness")
        assert initial_readiness.status_code == 200
        assert initial_readiness.json()["operational_ready"] is True
        assert initial_readiness.json()["business_documents_ready"] is False
        assert {
            item["key"]: item["status"]
            for item in initial_readiness.json()["checks"]
        } == {
            "database": "ready",
            "schema": "ready",
            "backup_storage": "ready",
            "daily_backup": "ready",
            "authentication": "ready",
            "farm_profile": "ready",
            "business_documents": "attention",
        }
        beds = client.get("/api/beds").json()
        crops = client.get("/api/crops").json()
        assert len(beds) == 6
        assert len(crops) >= 50
        assert {crop["category"] for crop in crops} >= {
            "Domača",
            "Azijska",
            "Indijska",
            "Baby leaf",
        }
        baby_leaf_names = {
            crop["name"] for crop in crops if crop["category"] == "Baby leaf"
        }
        assert baby_leaf_names >= {
            "Baby leaf mešanica",
            "Divja rukola",
            "Salatni trpotec",
            "Cikorija",
            "Mladi listi rdeče pese",
            "Baby leaf špinača",
            "Baby leaf ohrovt",
            "Baby leaf listna solata",
            "Baby leaf hrastov list",
            "Baby leaf rimska solata",
            "Baby leaf batavia",
            "Baby leaf endivija",
            "Baby leaf radič",
            "Baby leaf blitva",
            "Baby leaf gorčica",
            "Baby leaf mizuna",
            "Baby leaf tatsoi",
            "Baby leaf pak choi",
            "Baby leaf komatsuna",
            "Baby leaf kitajsko zelje",
        }
        assert len(baby_leaf_names) >= 20
        leaf_lettuce = next(
            crop for crop in crops if crop["name"] == "Baby leaf listna solata"
        )
        assert {variety["name"] for variety in leaf_lettuce["varieties"]} >= {
            "Green Saladbowl",
            "Red Saladbowl",
            "Tango",
            "Red Sails",
        }
        mixture_crop = next(crop for crop in crops if crop["name"] == "Baby leaf mešanica")
        classic_mixture = next(
            variety
            for variety in mixture_crop["varieties"]
            if variety["name"] == "Klasična solatna mešanica"
        )
        assert "baby špinača" in classic_mixture["composition"]
        assert "rdeče pese" in classic_mixture["composition"]
        supplier_varieties = [
            variety
            for crop in crops
            for variety in crop["varieties"]
            if variety["source_name"] == "Johnny's Selected Seeds"
        ]
        assert len(supplier_varieties) == 41
        assert all(
            variety["planting_method"] in {"direct", "transplant"}
            and variety["outdoor_months"]
            and variety["protected_months"]
            and variety["planting_calendar_note"]
            and variety["calendar_source_url"]
            for variety in supplier_varieties
        )
        assert all(
            variety["planting_method"] in {
                "direct", "transplant", "vegetative", "indoor_substrate"
            }
            and (variety["outdoor_months"] or variety["planting_method"] == "indoor_substrate")
            and variety["protected_months"]
            for crop in crops
            for variety in crop["varieties"]
        )
        assert all(
            variety["cultivation_methods"] and variety["harvest_methods"]
            for crop in crops
            for variety in crop["varieties"]
        )
        lettuce = next(crop for crop in crops if crop["name"] == "Solata")
        oakleaf_varieties = {
            variety["name"]: variety
            for variety in lettuce["varieties"]
            if variety["name"] in {
                "Green Saladbowl",
                "Red Saladbowl",
                "Panisse",
                "Oscarde",
            }
        }
        assert set(oakleaf_varieties) == {
            "Green Saladbowl",
            "Red Saladbowl",
            "Panisse",
            "Oscarde",
        }
        assert oakleaf_varieties["Green Saladbowl"]["days_baby"] == 30
        assert oakleaf_varieties["Red Saladbowl"]["days_to_harvest"] == 51
        assert oakleaf_varieties["Panisse"]["heat_tolerance"] == "visoka"
        assert "12" in oakleaf_varieties["Oscarde"]["protected_months"].split(",")
        for oakleaf in oakleaf_varieties.values():
            assert oakleaf["cultivation_methods"] == "direct,transplant"
            assert oakleaf["harvest_methods"] == (
                "full_size,baby_leaf,outer_leaves,cut_and_regrow"
            )
            assert oakleaf["nursery_days"] == 28
            assert oakleaf["direct_sow_extra_days"] == 14
            assert oakleaf["harvest_source_url"]
        endive = next(crop for crop in crops if crop["name"] == "Endivija")
        assert {variety["name"] for variety in endive["varieties"]} >= {
            "Dečja glava",
            "Eskariol zelena",
            "Dalmatinska kopica",
        }
        for endive_variety in endive["varieties"]:
            assert endive_variety["cultivation_methods"] == "direct,transplant"
            assert endive_variety["harvest_methods"] == (
                "full_size,baby_leaf,outer_leaves,cut_and_regrow"
            )
            assert endive_variety["nursery_days"] == 25
            assert endive_variety["direct_sow_extra_days"] == 18
            assert endive_variety["regrowth_interval_min_days"] == 5
            assert endive_variety["regrowth_interval_max_days"] == 14
            assert endive_variety["max_regrowth_cuts"] == 3
            assert endive_variety["harvest_source_url"]
        indian_chilli = next(
            crop for crop in crops if crop["name"] == "Indijski čili"
        )
        pusa_jwala = next(
            variety
            for variety in indian_chilli["varieties"]
            if variety["name"] == "Pusa Jwala"
        )
        pusa_sadabahar = next(
            variety
            for variety in indian_chilli["varieties"]
            if variety["name"] == "Pusa Sadabahar"
        )
        assert pusa_jwala["harvest_methods"] == "green_fruit,full_size"
        assert pusa_jwala["days_green_harvest"] == 80
        assert "svetlo zeleni" in pusa_jwala["traits"]
        assert pusa_sadabahar["days_green_harvest"] == 78
        assert pusa_sadabahar["harvest_interval_days"] == 7
        nepali_chilli = next(
            crop for crop in crops if crop["name"] == "Nepalski zeleni čili"
        )
        assert nepali_chilli["category"] == "Azijska"
        assert {variety["name"] for variety in nepali_chilli["varieties"]} == {
            "Suryamukhi",
            "Kantipure",
            "Jire Khursani",
            "Akabare Khursani",
        }
        suryamukhi = next(
            variety
            for variety in nepali_chilli["varieties"]
            if variety["name"] == "Suryamukhi"
        )
        kantipure = next(
            variety
            for variety in nepali_chilli["varieties"]
            if variety["name"] == "Kantipure"
        )
        assert suryamukhi["days_green_harvest"] == 83
        assert kantipure["days_green_harvest"] == 72
        assert all(
            variety["planting_method"] == "transplant"
            and variety["harvest_methods"] == "green_fruit,full_size"
            and variety["harvest_source_url"]
            for variety in nepali_chilli["varieties"]
        )
        requested = {
            crop["name"]: {variety["name"]: variety for variety in crop["varieties"]}
            for crop in crops
        }
        assert {"Toria", "Taro", "Chichinda", "Gobe"} <= requested.keys()
        assert {"Small Indian", "Large Indian"} <= requested["Karela"].keys()
        assert requested["Toria"]["TS-38"]["row_spacing_cm"] == 30.0
        assert requested["Taro"]["Sree Rashmi"]["planting_method"] == "vegetative"
        assert requested["Chichinda"]["CO-2"]["harvest_methods"] == "green_fruit"
        assert requested["Gobe"]["Ostrigar"]["cultivation_methods"] == "indoor_substrate"
        for crop_name, variety_name in {
            "Bamija": "Arka Anamika", "Azijska gorčica": "Pusa Sag-1",
            "Palak": "Pusa All Green", "Methi": "Indian Fenugreek",
            "Buča": "Arka Chandan", "Kumara": "Pusa Uday", "Grah": "Arkel",
            "Redkvica": "Pusa Chetki", "Fižol": "Arka Komal",
            "Lauki": "Pusa Naveen", "Koriander": "CO-4",
        }.items():
            variety = requested[crop_name][variety_name]
            assert variety["source_url"]
            assert variety["planting_calendar_note"]
            assert variety["harvest_methods"]
        astro = next(
            variety
            for variety in next(crop for crop in crops if crop["name"] == "Rukola")[
                "varieties"
            ]
            if variety["name"] == "Astro"
        )
        assert astro["days_to_harvest"] == 35
        assert astro["days_baby"] == 21
        assert astro["seed_spacing_cm"] == 0.5
        assert astro["heat_tolerance"] == "visoka"
        assert astro["cold_tolerance"] == "visoka"
        assert astro["outdoor_months"] == "3,4,5,6,7,8,9,10"
        assert astro["succession_interval_days"] == 14
        assert "zaporedne setve" in astro["slovenia_note"]
        methi = next(
            variety
            for variety in next(crop for crop in crops if crop["name"] == "Methi")[
                "varieties"
            ]
            if variety["name"] == "Kasuri"
        )
        assert methi["planting_method"] == "direct"
        assert methi["outdoor_months"] == "2,3,4,5,8,9,10"
        malabar_spinach = next(
            variety
            for variety in next(
                crop for crop in crops if crop["name"] == "Malabarska špinača"
            )["varieties"]
            if variety["name"] == "Green Stem"
        )
        assert malabar_spinach["planting_method"] == "direct"
        assert malabar_spinach["heat_tolerance"] == "visoka"
        mountain_magic = next(
            variety
            for variety in next(
                crop for crop in crops if crop["name"] == "Paradižnik"
            )["varieties"]
            if variety["name"] == "Mountain Magic"
        )
        assert mountain_magic["days_to_harvest"] == 66
        assert "krompirjevi plesni" in mountain_magic["traits"]
        with SessionLocal() as db:
            crop_count = db.scalar(select(func.count()).select_from(Crop))
            variety_count = db.scalar(select(func.count()).select_from(Variety))
            seed_database(db)
            seed_database(db)
            assert db.scalar(select(func.count()).select_from(Crop)) == crop_count
            assert (
                db.scalar(select(func.count()).select_from(Variety))
                == variety_count
            )

        new_crop = client.post(
            "/api/crops",
            json={
                "name": "Testna zelenjava",
                "family": "Testaceae",
                "category": "Lastna",
            },
        )
        assert new_crop.status_code == 201
        assert new_crop.json()["varieties"] == []
        assert client.post(
            "/api/crops",
            json={
                "name": "testna zelenjava",
                "family": "Testaceae",
                "category": "Lastna",
            },
        ).status_code == 409
        assert client.post(
            "/api/crops",
            json={"name": " ", "family": " ", "category": "Plodovke"},
        ).status_code == 422
        new_variety = client.post(
            f"/api/crops/{new_crop.json()['id']}/varieties",
            json={
                "name": "Testna sorta",
                "days_to_harvest": 80,
                "days_spring": 80,
                "days_summer": 60,
                "days_autumn": 95,
                "days_winter": 120,
                "composition": "  Testna solata, rukola in špinača.  ",
            },
        )
        assert new_variety.status_code == 201
        assert new_variety.json()["days_to_harvest"] == 80
        assert new_variety.json()["composition"] == (
            "Testna solata, rukola in špinača."
        )
        assert new_variety.json()["planting_method"] == "direct"
        assert new_variety.json()["cultivation_methods"] == "direct"
        assert new_variety.json()["harvest_methods"] == "full_size"
        assert new_variety.json()["outdoor_months"] == "3,4,5,6,7,8,9"
        assert "splošno priporočilo" in new_variety.json()[
            "planting_calendar_note"
        ]
        assert {
            key: new_variety.json()[key]
            for key in (
                "days_spring",
                "days_summer",
                "days_autumn",
                "days_winter",
            )
        } == {
            "days_spring": 80,
            "days_summer": 60,
            "days_autumn": 95,
            "days_winter": 120,
        }
        assert client.post(
            f"/api/crops/{new_crop.json()['id']}/varieties",
            json={"name": "testna sorta", "days_to_harvest": 90},
        ).status_code == 409
        refreshed_crops = client.get("/api/crops").json()
        refreshed_crop = next(
            item for item in refreshed_crops if item["name"] == "Testna zelenjava"
        )
        assert refreshed_crop["varieties"] == [new_variety.json()]

        crop = next(item for item in crops if item["name"] == "Rukola")
        variety = next(item for item in crop["varieties"] if item["name"] == "Astro")
        bed = next(item for item in beds if item["name"] == "A3")
        suggestions = client.post(
            "/api/planting-suggestions",
            json={
                "crop_id": crop["id"],
                "variety_id": variety["id"],
                "sowing_date": "2026-08-05",
            },
        )
        assert suggestions.status_code == 200
        suggestion_data = suggestions.json()
        assert suggestion_data["empty_beds"] == 6
        assert suggestion_data["occupied_beds"] == 0
        assert len(suggestion_data["recommended_beds"]) == 5
        assert all(
            item["rotation_safe"] for item in suggestion_data["recommended_beds"]
        )
        assert "A1" not in {
            item["bed"] for item in suggestion_data["recommended_beds"]
        }
        assert len(suggestion_data["planting_ideas"]) == 6
        assert len(
            {item["bed_id"] for item in suggestion_data["planting_ideas"]}
        ) == 6
        assert all(
            item["rotation_safe"] and not item["has_plan_conflict"]
            for item in suggestion_data["planting_ideas"]
        )

        new_bed = client.post(
            "/api/beds",
            json={"name": "B1", "width_m": 0.8, "length_m": 15},
        )
        assert new_bed.status_code == 201
        assert new_bed.json()["area_m2"] == 12.0
        resized_bed = client.put(
            f"/api/beds/{new_bed.json()['id']}/size",
            json={"width_m": 1.2, "length_m": 20},
        )
        assert resized_bed.status_code == 200
        assert resized_bed.json()["area_m2"] == 24.0
        assert client.get(f"/api/beds/{new_bed.json()['id']}").json()[
            "length_m"
        ] == 20
        assert client.put(
            f"/api/beds/{new_bed.json()['id']}/size",
            json={"width_m": 0, "length_m": 20},
        ).status_code == 422

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
        assert planting.json()["maturity_season"] == "summer"
        assert planting.json()["maturity_season_label"] == "poletje"
        assert planting.json()["maturity_days"] == variety["days_summer"]
        assert planting.json()["expected_harvest_date"] == "2026-09-06"

        detail = client.get(f"/api/beds/{bed['id']}")
        assert detail.status_code == 200
        assert detail.json()["current_planting"]["variety"] == "Astro"
        planting_tasks = [
            item
            for item in detail.json()["tasks"]
            if item["planting_id"] == planting.json()["id"]
        ]
        assert len(planting_tasks) == 3

        task_review = client.get(
            "/api/task-review?date=2026-08-05&horizon_days=7"
        )
        assert task_review.status_code == 200
        review_data = task_review.json()
        assert review_data["reviewed_beds"] == 7
        assert review_data["active_beds"] == 1
        assert review_data["suggestion_count"] >= 1
        assert {item["task_type"] for item in review_data["suggestions"]} == {
            "bed_planning"
        }
        b1_planning = next(
            item
            for item in review_data["suggestions"]
            if item["bed_id"] == new_bed.json()["id"]
        )
        applied_review = client.post(
            "/api/task-review/apply",
            json={
                "review_date": "2026-08-05",
                "horizon_days": 7,
                "selected_keys": [b1_planning["key"]],
            },
        )
        assert applied_review.status_code == 201
        assert applied_review.json()["created_count"] == 1
        repeated_review = client.get(
            "/api/task-review?date=2026-08-05&horizon_days=7"
        ).json()
        assert b1_planning["key"] not in {
            item["key"] for item in repeated_review["suggestions"]
        }
        stale_apply = client.post(
            "/api/task-review/apply",
            json={
                "review_date": "2026-08-05",
                "horizon_days": 7,
                "selected_keys": [b1_planning["key"]],
            },
        )
        assert stale_apply.status_code == 201
        assert stale_apply.json()["created_count"] == 0
        assert stale_apply.json()["skipped_count"] == 1

        worker = client.post(
            "/api/workers",
            json={
                "name": "Maja Kovač",
                "role": "Pridelava",
                "hourly_rate_eur": 12,
            },
        )
        assert worker.status_code == 201
        worker_data = worker.json()
        assert worker_data["hourly_rate_eur"] == 12
        assert client.post(
            "/api/workers",
            json={"name": "maja kovač", "hourly_rate_eur": 15},
        ).status_code == 409
        assert len(client.get("/api/workers").json()) == 1

        invalid_labor_task = client.post(
            f"/api/tasks/{planting_tasks[1]['id']}/complete",
            json={"worker_id": worker_data["id"], "duration_minutes": 0},
        )
        assert invalid_labor_task.status_code == 422

        task = planting_tasks[0]
        completed = client.post(
            f"/api/tasks/{task['id']}/complete",
            json={
                "duration_minutes": 25,
                "worker_id": worker_data["id"],
                "quantity_used": 120,
                "unit": "L",
                "notes": "Pregled in zalivanje zaključena.",
            },
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert completed.json()["duration_minutes"] == 25
        assert completed.json()["labor_worker"] == "Maja Kovač"
        assert completed.json()["labor_cost_eur"] == 5

        manual_labor = client.post(
            "/api/labor-entries",
            json={
                "worker_id": worker_data["id"],
                "work_date": "2026-09-12",
                "duration_minutes": 90,
                "hourly_rate_eur": 15,
                "description": "Splošna priprava orodja",
            },
        )
        assert manual_labor.status_code == 201
        assert manual_labor.json()["bed"] is None
        assert manual_labor.json()["hours"] == 1.5
        assert manual_labor.json()["total_cost_eur"] == 22.5
        assert client.post(
            "/api/labor-entries",
            json={
                "worker_id": 999999,
                "work_date": "2026-09-12",
                "duration_minutes": 30,
                "description": "Neveljaven izvajalec",
            },
        ).status_code == 404

        labor_report = client.get(
            "/api/labor-report?start=2026-08-01&end=2026-09-30"
        )
        assert labor_report.status_code == 200
        labor_data = labor_report.json()
        assert labor_data["summary"] == {
            "entry_count": 2,
            "duration_minutes": 115,
            "hours": 1.92,
            "cost_eur": 27.5,
            "unallocated_hours": 1.5,
            "unallocated_cost_eur": 22.5,
        }
        assert labor_data["by_worker"][0]["cost_eur"] == 27.5
        assert labor_data["by_bed"][0]["bed"] == bed["name"]
        assert labor_data["by_bed"][0]["cost_eur"] == 5
        assert len(labor_data["entries"]) == 2
        assert client.get(
            "/api/labor-report?start=2026-10-01&end=2026-09-30"
        ).status_code == 422

        finished = client.post(f"/api/plantings/{planting.json()['id']}/finish")
        assert finished.status_code == 200
        refreshed_bed = client.get(f"/api/beds/{bed['id']}").json()
        assert refreshed_bed["status"] == "empty"
        assert refreshed_bed["last_crop_family"] == "Brassicaceae"
        suggestions_after_cycle = client.post(
            "/api/planting-suggestions",
            json={
                "crop_id": crop["id"],
                "variety_id": variety["id"],
                "sowing_date": "2026-09-20",
            },
        ).json()
        assert "A3" not in {
            item["bed"] for item in suggestions_after_cycle["recommended_beds"]
        }

        with SessionLocal() as db:
            lettuce = db.scalar(select(Crop).where(Crop.name == "Solata"))
            lettuce_variety = db.scalar(
                select(Variety)
                .where(Variety.crop_id == lettuce.id)
                .order_by(Variety.id)
            )
            stored_bed = db.get(Bed, bed["id"])
            second_cycle = Planting(
                farm_id=1,
                bed_id=stored_bed.id,
                crop_id=lettuce.id,
                variety_id=lettuce_variety.id,
                sowing_date=date(2026, 9, 20),
                expected_harvest_date=date(2026, 11, 5),
                status="completed",
            )
            db.add(second_cycle)
            stored_bed.last_crop_family = lettuce.family
            db.commit()
            second_cycle_id = second_cycle.id
        suggestions_after_two_cycles = client.post(
            "/api/planting-suggestions",
            json={
                "crop_id": crop["id"],
                "variety_id": variety["id"],
                "sowing_date": "2026-11-10",
            },
        ).json()
        assert "A3" not in {
            item["bed"]
            for item in suggestions_after_two_cycles["recommended_beds"]
        }
        with SessionLocal() as db:
            db.delete(db.get(Planting, second_cycle_id))
            db.get(Bed, bed["id"]).last_crop_family = crop["family"]
            db.commit()

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
        assert bed_economics["direct_costs_eur"] == 42.5
        assert bed_economics["material_costs_eur"] == 0
        assert bed_economics["labor_costs_eur"] == 5
        assert bed_economics["costs_eur"] == 47.5
        assert bed_economics["revenue_eur"] == 90
        assert bed_economics["profit_eur"] == 42.5

        customer = client.post(
            "/api/customers",
            json={
                "name": "Bistro Zeleno",
                "email": "narocila@example.com",
                "phone": "+386 40 000 000",
                "address": "Tržna ulica 1, Ljubljana",
                "customer_type": "business",
                "tax_number": "SI12345678",
            },
        )
        assert customer.status_code == 201

        price_a = client.put(
            f"/api/price-list/{crop['id']}",
            json={"quality": "A", "price_per_kg_eur": 7},
        )
        assert price_a.status_code == 200
        assert price_a.json()["crop"] == "Rukola"
        assert price_a.json()["price_per_kg_eur"] == 7
        price_b = client.put(
            f"/api/price-list/{crop['id']}",
            json={"quality": "B", "price_per_kg_eur": 5},
        )
        assert price_b.status_code == 200
        prices = client.get("/api/price-list")
        assert prices.status_code == 200
        assert [(item["quality"], item["price_per_kg_eur"]) for item in prices.json()] == [
            ("A", 7),
            ("B", 5),
        ]

        inventory = client.get("/api/inventory").json()
        stock = next(item for item in inventory if item["harvest_id"] == harvest.json()["id"])
        assert stock["available_kg"] == 3.5
        assert stock["reserved_kg"] == 0
        assert stock["crop_id"] == crop["id"]
        assert stock["suggested_price_per_kg_eur"] == 7

        reserved_order = client.post(
            "/api/orders",
            json={
                "customer_id": customer.json()["id"],
                "order_date": "2026-09-10",
                "delivery_date": "2026-09-11",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 3,
                        "price_per_kg_eur": 6.5,
                    }
                ],
            },
        )
        assert reserved_order.status_code == 201
        assert reserved_order.json()["status"] == "confirmed"
        assert reserved_order.json()["total_eur"] == 19.5

        reserved_stock = client.get("/api/inventory").json()
        reserved_stock = next(
            item for item in reserved_stock if item["harvest_id"] == harvest.json()["id"]
        )
        assert reserved_stock["reserved_kg"] == 3
        assert reserved_stock["available_kg"] == 0.5

        sale_into_reservation = client.post(
            "/api/sales",
            json={
                "harvest_id": harvest.json()["id"],
                "sale_date": "2026-09-10",
                "quantity_kg": 1,
                "price_per_kg_eur": 6,
            },
        )
        assert sale_into_reservation.status_code == 409

        unavailable_order = client.post(
            "/api/orders",
            json={
                "customer_id": customer.json()["id"],
                "order_date": "2026-09-10",
                "delivery_date": "2026-09-11",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 1,
                        "price_per_kg_eur": 6.5,
                    }
                ],
            },
        )
        assert unavailable_order.status_code == 409

        delivery_note = client.get(
            f"/api/orders/{reserved_order.json()['id']}/document?document_type=delivery_note"
        )
        assert delivery_note.status_code == 200
        assert delivery_note.json()["document_number"].startswith("D-")

        cancelled = client.post(
            f"/api/orders/{reserved_order.json()['id']}/status",
            json={"status": "cancelled"},
        )
        assert cancelled.status_code == 200
        released_stock = client.get("/api/inventory").json()
        released_stock = next(
            item for item in released_stock if item["harvest_id"] == harvest.json()["id"]
        )
        assert released_stock["available_kg"] == 3.5

        fulfilled_order = client.post(
            "/api/orders",
            json={
                "customer_id": customer.json()["id"],
                "order_date": "2026-09-11",
                "delivery_date": "2026-09-12",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 2,
                        "price_per_kg_eur": 7,
                    }
                ],
            },
        )
        assert fulfilled_order.status_code == 201
        fulfilled = client.post(
            f"/api/orders/{fulfilled_order.json()['id']}/status",
            json={"status": "fulfilled"},
        )
        assert fulfilled.status_code == 200
        invoice = client.get(
            f"/api/orders/{fulfilled_order.json()['id']}/document?document_type=invoice"
        )
        assert invoice.status_code == 410

        farm_profile = client.put(
            "/api/farm-profile",
            json={
                "basic_agriculture_invoice_exemption": True,
                "farm_name": "Kmetija Zeleni Gaj",
                "seller_tax_number": "SI87654321",
                "seller_address": "Poljska pot 5, 1000 Ljubljana",
                "seller_iban": "SI56191000000123456",
                "seller_registration_number": "1234567000",
                "vat_note": "DDV ni obračunan v skladu s posebnim režimom.",
                "business_premise_code": "GM",
                "device_code": "01",
                "default_due_days": 14,
            },
        )
        assert farm_profile.status_code == 200
        assert farm_profile.json()["business_documents_ready"] is True
        assert client.get("/api/sales-settings").json()["seller_name"] == (
            "Kmetija Zeleni Gaj"
        )
        assert client.get("/api/invoice-profile").json()["seller_address"] == (
            "Poljska pot 5, 1000 Ljubljana"
        )
        archived_invoice = client.post(
            "/api/invoices",
            json={
                "source_type": "order",
                "source_id": fulfilled_order.json()["id"],
                "issued_on": "2026-09-12",
                "payment_method": "bank_transfer",
            },
        )
        assert archived_invoice.status_code == 201
        archived_invoice_data = archived_invoice.json()
        assert archived_invoice_data["number"] == "R-GM-01-2026-0001"
        assert archived_invoice_data["due_date"] == "2026-09-26"
        assert archived_invoice_data["fiscal_status"] == "not_required"
        assert archived_invoice_data["customer"]["tax_number"] == "SI12345678"
        assert archived_invoice_data["lines"][0]["line_total_eur"] == 14
        assert len(archived_invoice_data["pdf_sha256"]) == 64
        invoice_pdf = client.get(
            f"/api/invoices/{archived_invoice_data['id']}/pdf"
        )
        assert invoice_pdf.status_code == 200
        assert invoice_pdf.headers["content-type"] == "application/pdf"
        assert invoice_pdf.content.startswith(b"%PDF")
        assert client.get(
            f"/api/invoices/{archived_invoice_data['id']}/pdf"
        ).content == invoice_pdf.content
        duplicate_invoice = client.post(
            "/api/invoices",
            json={
                "source_type": "order",
                "source_id": fulfilled_order.json()["id"],
                "issued_on": "2026-09-13",
            },
        )
        assert duplicate_invoice.status_code == 409

        final_stock = client.get("/api/inventory").json()
        final_stock = next(
            item for item in final_stock if item["harvest_id"] == harvest.json()["id"]
        )
        assert final_stock["sold_kg"] == 17
        assert final_stock["reserved_kg"] == 0
        assert final_stock["available_kg"] == 1.5

        future_order = client.post(
            "/api/orders",
            json={
                "customer_id": customer.json()["id"],
                "order_date": "2026-09-15",
                "delivery_date": "2026-09-25",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 1,
                        "price_per_kg_eur": 7,
                    }
                ],
            },
        )
        assert future_order.status_code == 201

        plan_series = client.post(
            "/api/plans",
            json={
                "bed_id": bed["id"],
                "crop_id": crop["id"],
                "variety_id": variety["id"],
                "sowing_date": "2026-09-20",
                "transplant_date": "2026-09-27",
                "expected_harvest_date": "2026-10-25",
                "expected_yield_kg": 8,
                "succession_count": 2,
                "succession_interval_days": 14,
                "notes": "Jesenska zaporedna setev",
            },
        )
        assert plan_series.status_code == 201
        assert len(plan_series.json()["plans"]) == 2
        assert plan_series.json()["warnings"]
        assert plan_series.json()["plans"][0]["maturity_season"] == "autumn"
        assert plan_series.json()["plans"][0]["maturity_days"] == variety[
            "days_autumn"
        ]
        assert plan_series.json()["plans"][0]["expected_harvest_date"] == "2026-10-25"
        assert plan_series.json()["plans"][1]["expected_harvest_date"] == "2026-11-08"

        invalid_harvest_date = client.post(
            "/api/plans",
            json={
                "bed_id": bed["id"],
                "crop_id": crop["id"],
                "variety_id": variety["id"],
                "sowing_date": "2026-09-20",
                "transplant_date": "2026-09-27",
                "expected_harvest_date": "2026-09-26",
                "expected_yield_kg": 8,
            },
        )
        assert invalid_harvest_date.status_code == 422

        calendar = client.get(
            "/api/planning/calendar?start=2026-09-20&end=2026-11-30"
        )
        assert calendar.status_code == 200
        event_types = {event["type"] for event in calendar.json()["events"]}
        assert {"sowing", "transplant", "planned_harvest", "delivery"} <= event_types

        forecast = client.get(
            "/api/planning/forecast?start=2026-09-20&end=2026-11-30"
        )
        assert forecast.status_code == 200
        crop_forecast = next(
            item for item in forecast.json()["rows"] if item["crop_id"] == crop["id"]
        )
        assert crop_forecast["current_stock_kg"] == 1.5
        assert crop_forecast["planned_yield_kg"] == 16
        assert crop_forecast["confirmed_demand_kg"] == 1
        assert crop_forecast["projected_balance_kg"] == 16.5

        first_plan, second_plan = plan_series.json()["plans"]
        rotation_blocked = client.post(
            f"/api/plans/{first_plan['id']}/activate",
            json={"override_rotation": False},
        )
        assert rotation_blocked.status_code == 409
        activated = client.post(
            f"/api/plans/{first_plan['id']}/activate",
            json={"override_rotation": True},
        )
        assert activated.status_code == 200
        assert activated.json()["plan"]["status"] == "activated"
        assert activated.json()["planting_id"]

        cancelled_plan = client.post(
            f"/api/plans/{second_plan['id']}/status",
            json={"status": "cancelled"},
        )
        assert cancelled_plan.status_code == 200
        visible_plans = client.get("/api/plans").json()
        assert len(visible_plans) == 1
        assert visible_plans[0]["status"] == "activated"

        settings = client.get("/api/sales-settings")
        assert settings.status_code == 200
        assert settings.json()["basic_agriculture_invoice_exemption"] is True

        second_quality_harvest = client.post(
            "/api/harvests",
            json={
                "planting_id": planting.json()["id"],
                "harvest_date": "2026-09-20",
                "quantity_kg": 1,
                "quality": "B",
                "notes": "Druga kakovost za tržnico.",
            },
        )
        assert second_quality_harvest.status_code == 201
        basket_inventory = client.get("/api/inventory").json()
        second_stock = next(
            item for item in basket_inventory
            if item["harvest_id"] == second_quality_harvest.json()["id"]
        )
        assert second_stock["suggested_price_per_kg_eur"] == 5

        anonymous_sale = client.post(
            "/api/retail-sales",
            json={
                "sale_date": "2026-09-20",
                "payment_method": "cash",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 0.4,
                        "price_per_kg_eur": 7,
                    },
                    {
                        "harvest_id": second_quality_harvest.json()["id"],
                        "quantity_kg": 0.2,
                        "price_per_kg_eur": 5,
                    },
                ],
            },
        )
        assert anonymous_sale.status_code == 201
        assert anonymous_sale.json()["customer"] == "Končni potrošnik"
        assert anonymous_sale.json()["customer_type"] == "consumer"
        assert anonymous_sale.json()["invoice_required"] is False
        assert anonymous_sale.json()["total_eur"] == 3.8
        assert len(anonymous_sale.json()["items"]) == 2

        receipt = client.get(
            f"/api/retail-sales/{anonymous_sale.json()['id']}/document?document_type=receipt"
        )
        assert receipt.status_code == 200
        assert receipt.json()["document_number"].startswith("P-")
        consumer_invoice = client.get(
            f"/api/retail-sales/{anonymous_sale.json()['id']}/document?document_type=invoice"
        )
        assert consumer_invoice.status_code == 409

        business_sale = client.post(
            "/api/retail-sales",
            json={
                "customer_id": customer.json()["id"],
                "sale_date": "2026-09-20",
                "payment_method": "card",
                "items": [
                    {
                        "harvest_id": harvest.json()["id"],
                        "quantity_kg": 0.1,
                        "price_per_kg_eur": 7,
                    }
                ],
            },
        )
        assert business_sale.status_code == 201
        assert business_sale.json()["customer_type"] == "business"
        assert business_sale.json()["invoice_required"] is True
        business_invoice = client.get(
            f"/api/retail-sales/{business_sale.json()['id']}/document?document_type=invoice"
        )
        assert business_invoice.status_code == 410

        fiscal_invoice = client.post(
            "/api/invoices",
            json={
                "source_type": "retail_sale",
                "source_id": business_sale.json()["id"],
                "issued_on": "2026-09-20",
            },
        )
        assert fiscal_invoice.status_code == 201
        fiscal_invoice_data = fiscal_invoice.json()
        assert fiscal_invoice_data["number"] == "R-GM-01-2026-0002"
        assert fiscal_invoice_data["fiscal_status"] == "pending"
        pending_pdf = client.get(
            f"/api/invoices/{fiscal_invoice_data['id']}/pdf"
        )
        assert pending_pdf.status_code == 409
        confirmation = client.post(
            f"/api/invoices/{fiscal_invoice_data['id']}/fiscal-confirmation",
            json={"eor": "EOR-RAČUN-001", "zoi": "ZOI-RAČUN-001"},
        )
        assert confirmation.status_code == 200
        assert confirmation.json()["fiscal_status"] == "confirmed"
        assert len(confirmation.json()["pdf_sha256"]) == 64
        locked_confirmation = client.post(
            f"/api/invoices/{fiscal_invoice_data['id']}/fiscal-confirmation",
            json={"eor": "DRUG-EOR"},
        )
        assert locked_confirmation.status_code == 409
        confirmed_pdf = client.get(
            f"/api/invoices/{fiscal_invoice_data['id']}/pdf"
        )
        assert confirmed_pdf.status_code == 200
        assert confirmed_pdf.content.startswith(b"%PDF")

        retail_stock = client.get("/api/inventory").json()
        retail_stock = next(
            item for item in retail_stock if item["harvest_id"] == harvest.json()["id"]
        )
        assert retail_stock["available_kg"] == 0

        sales_report = client.get(
            "/api/sales-report?start=2026-09-12&end=2026-09-20"
        )
        assert sales_report.status_code == 200
        report = sales_report.json()
        assert report["summary"] == {
            "transactions": 3,
            "total_eur": 18.5,
            "cash_eur": 3.8,
            "card_eur": 0.7,
            "bank_transfer_eur": 0,
            "invoice_eur": 14.7,
            "unclassified_eur": 0,
            "consumer_eur": 3.8,
            "business_eur": 14.7,
            "invoice_count": 2,
        }
        assert len(report["daily"]) == 2
        assert report["daily"][0]["date"] == "2026-09-20"
        assert {entry["source"] for entry in report["entries"]} == {
            "retail_sale",
            "order",
        }
        order_entry = next(
            entry for entry in report["entries"] if entry["source"] == "order"
        )
        assert order_entry["payment_method"] == "invoice"

        sales_csv = client.get(
            "/api/sales-report/export.csv?start=2026-09-12&end=2026-09-20"
        )
        assert sales_csv.status_code == 200
        assert sales_csv.headers["content-type"].startswith("text/csv")
        assert "GM-2026" in sales_csv.text
        assert "Končni potrošnik" in sales_csv.text

        invalid_report = client.get(
            "/api/sales-report?start=2026-09-21&end=2026-09-20"
        )
        assert invalid_report.status_code == 422

        before_delivery = client.get("/api/receivables?as_of=2026-09-11")
        assert before_delivery.status_code == 200
        assert before_delivery.json()["summary"]["invoice_count"] == 0
        assert before_delivery.json()["items"] == []

        overdue_receivables = client.get("/api/receivables?as_of=2026-09-27")
        assert overdue_receivables.status_code == 200
        assert overdue_receivables.json()["summary"] == {
            "invoice_count": 1,
            "open_count": 1,
            "overdue_count": 1,
            "invoiced_eur": 14,
            "paid_eur": 0,
            "outstanding_eur": 14,
            "overdue_eur": 14,
        }
        receivable = overdue_receivables.json()["items"][0]
        assert receivable["order_id"] == fulfilled_order.json()["id"]
        assert receivable["due_date"] == "2026-09-26"
        assert receivable["status"] == "overdue"
        assert receivable["days_overdue"] == 1

        partial_payment = client.post(
            f"/api/orders/{fulfilled_order.json()['id']}/payments",
            json={
                "payment_date": "2026-09-20",
                "amount_eur": 4,
                "payment_method": "bank_transfer",
                "notes": "Delno nakazilo",
            },
        )
        assert partial_payment.status_code == 201
        assert partial_payment.json()["status"] == "partial"
        assert partial_payment.json()["paid_eur"] == 4
        assert partial_payment.json()["outstanding_eur"] == 10

        overpayment = client.post(
            f"/api/orders/{fulfilled_order.json()['id']}/payments",
            json={
                "payment_date": "2026-09-21",
                "amount_eur": 11,
                "payment_method": "bank_transfer",
            },
        )
        assert overpayment.status_code == 409

        final_payment = client.post(
            f"/api/orders/{fulfilled_order.json()['id']}/payments",
            json={
                "payment_date": "2026-09-21",
                "amount_eur": 10,
                "payment_method": "bank_transfer",
            },
        )
        assert final_payment.status_code == 201
        assert final_payment.json()["status"] == "paid"
        assert final_payment.json()["outstanding_eur"] == 0
        assert len(final_payment.json()["payments"]) == 2

        historical_receivables = client.get(
            "/api/receivables?as_of=2026-09-20&include_paid=true"
        )
        historical = historical_receivables.json()["items"][0]
        assert historical["status"] == "partial"
        assert historical["paid_eur"] == 4
        assert historical["outstanding_eur"] == 10
        assert len(historical["payments"]) == 1

        open_receivables = client.get("/api/receivables?as_of=2026-09-27")
        assert open_receivables.status_code == 200
        assert open_receivables.json()["items"] == []
        assert open_receivables.json()["summary"]["paid_eur"] == 14
        assert open_receivables.json()["summary"]["outstanding_eur"] == 0

        paid_receivables = client.get(
            "/api/receivables?as_of=2026-09-27&include_paid=true"
        )
        assert len(paid_receivables.json()["items"]) == 1
        assert paid_receivables.json()["items"][0]["status"] == "paid"

        cash_flow = client.get(
            "/api/cash-flow?start=2026-09-09&end=2026-09-21"
        )
        assert cash_flow.status_code == 200
        flow = cash_flow.json()
        assert flow["summary"] == {
            "inflow_eur": 18.5,
            "outflow_eur": 42.5,
            "net_eur": -24,
            "inflow_count": 4,
            "outflow_count": 1,
            "refund_eur": 0,
            "refund_count": 0,
            "supplier_payments_eur": 0,
            "supplier_payment_count": 0,
            "cash_eur": 3.8,
            "card_eur": 0.7,
            "bank_transfer_eur": 14,
            "costs_by_category": {"labor": 42.5},
        }
        assert len(flow["entries"]) == 5
        assert {entry["source"] for entry in flow["entries"]} == {
            "retail_sale",
            "order_payment",
            "cost",
        }
        assert [day["date"] for day in flow["daily"]] == [
            "2026-09-21",
            "2026-09-20",
            "2026-09-09",
        ]
        assert flow["daily"][0]["net_eur"] == 10
        assert flow["daily"][1]["inflow_eur"] == 8.5
        assert flow["daily"][2]["net_eur"] == -42.5

        cash_flow_csv = client.get(
            "/api/cash-flow/export.csv?start=2026-09-09&end=2026-09-21"
        )
        assert cash_flow_csv.status_code == 200
        assert cash_flow_csv.headers["content-type"].startswith("text/csv")
        assert "Plačilo računa" in cash_flow_csv.text
        assert "Pobiranje in pakiranje" in cash_flow_csv.text

        invalid_cash_flow = client.get(
            "/api/cash-flow?start=2026-09-22&end=2026-09-21"
        )
        assert invalid_cash_flow.status_code == 422

        credit_note = client.post(
            f"/api/invoices/{fiscal_invoice_data['id']}/credit-notes",
            json={
                "issued_on": "2026-09-22",
                "reason": "Napačno evidentirana poslovna prodaja.",
            },
        )
        assert credit_note.status_code == 201
        credit_note_data = credit_note.json()
        assert credit_note_data["number"] == "DB-GM-01-2026-0001"
        assert credit_note_data["fiscal_status"] == "pending"
        assert credit_note_data["paid_eur"] == 0.7
        assert credit_note_data["refunded_eur"] == 0
        assert credit_note_data["refundable_eur"] == 0.7
        assert credit_note_data["refunds"] == []
        assert client.get(
            f"/api/credit-notes/{credit_note_data['id']}/pdf"
        ).status_code == 409
        pending_refund = client.post(
            f"/api/credit-notes/{credit_note_data['id']}/refunds",
            json={
                "refund_date": "2026-09-23",
                "amount_eur": 0.4,
                "payment_method": "card",
            },
        )
        assert pending_refund.status_code == 409
        credit_confirmation = client.post(
            f"/api/credit-notes/{credit_note_data['id']}/fiscal-confirmation",
            json={"eor": "EOR-DOBROPIS-001", "zoi": "ZOI-DOBROPIS-001"},
        )
        assert credit_confirmation.status_code == 200
        assert len(credit_confirmation.json()["pdf_sha256"]) == 64
        credit_pdf = client.get(
            f"/api/credit-notes/{credit_note_data['id']}/pdf"
        )
        assert credit_pdf.status_code == 200
        assert credit_pdf.content.startswith(b"%PDF")

        partial_refund = client.post(
            f"/api/credit-notes/{credit_note_data['id']}/refunds",
            json={
                "refund_date": "2026-09-23",
                "amount_eur": 0.4,
                "payment_method": "card",
                "notes": "Delno vračilo",
            },
        )
        assert partial_refund.status_code == 201
        assert partial_refund.json()["credit_note"]["refunded_eur"] == 0.4
        assert partial_refund.json()["credit_note"]["refundable_eur"] == 0.3

        over_refund = client.post(
            f"/api/credit-notes/{credit_note_data['id']}/refunds",
            json={
                "refund_date": "2026-09-23",
                "amount_eur": 0.31,
                "payment_method": "card",
            },
        )
        assert over_refund.status_code == 409

        final_refund = client.post(
            f"/api/credit-notes/{credit_note_data['id']}/refunds",
            json={
                "refund_date": "2026-09-23",
                "amount_eur": 0.3,
                "payment_method": "card",
            },
        )
        assert final_refund.status_code == 201
        assert final_refund.json()["credit_note"]["refunded_eur"] == 0.7
        assert final_refund.json()["credit_note"]["refundable_eur"] == 0
        assert len(final_refund.json()["credit_note"]["refunds"]) == 2
        assert client.post(
            f"/api/credit-notes/{credit_note_data['id']}/refunds",
            json={
                "refund_date": "2026-09-24",
                "amount_eur": 0.01,
                "payment_method": "cash",
            },
        ).status_code == 409

        refund_cash_flow = client.get(
            "/api/cash-flow?start=2026-09-23&end=2026-09-23"
        )
        assert refund_cash_flow.status_code == 200
        refund_flow = refund_cash_flow.json()
        assert refund_flow["summary"] == {
            "inflow_eur": 0,
            "outflow_eur": 0.7,
            "net_eur": -0.7,
            "inflow_count": 0,
            "outflow_count": 2,
            "refund_eur": 0.7,
            "refund_count": 2,
            "supplier_payments_eur": 0,
            "supplier_payment_count": 0,
            "cash_eur": 0,
            "card_eur": 0,
            "bank_transfer_eur": 0,
            "costs_by_category": {},
        }
        assert len(refund_flow["entries"]) == 2
        assert {entry["source"] for entry in refund_flow["entries"]} == {"refund"}
        assert {entry["method"] for entry in refund_flow["entries"]} == {"card"}
        assert {entry["reference"] for entry in refund_flow["entries"]} == {
            "DB-GM-01-2026-0001"
        }
        refund_cash_flow_csv = client.get(
            "/api/cash-flow/export.csv?start=2026-09-23&end=2026-09-23"
        )
        assert refund_cash_flow_csv.status_code == 200
        assert "Vračilo po dobropisu" in refund_cash_flow_csv.text
        assert "DB-GM-01-2026-0001" in refund_cash_flow_csv.text
        assert client.post(
            f"/api/invoices/{fiscal_invoice_data['id']}/credit-notes",
            json={"issued_on": "2026-09-23", "reason": "Drugi dobropis"},
        ).status_code == 409

        archived_documents = client.get("/api/invoices")
        assert archived_documents.status_code == 200
        assert len(archived_documents.json()) == 2
        credited = next(
            item for item in archived_documents.json()
            if item["id"] == fiscal_invoice_data["id"]
        )
        assert credited["status"] == "credited"
        assert credited["credit_note"]["number"] == "DB-GM-01-2026-0001"
        assert credited["credit_note"]["refunded_eur"] == 0.7
        assert credited["credit_note"]["refundable_eur"] == 0
        assert len(credited["credit_note"]["refunds"]) == 2
        assert invalid_cash_flow.status_code == 422

        close_preview = client.get(
            "/api/day-closes/preview?business_date=2026-09-20&opening_cash_eur=50"
        )
        assert close_preview.status_code == 200
        preview = close_preview.json()
        assert preview["closed"] is False
        assert preview["opening_cash_eur"] == 50
        assert preview["cash_in_eur"] == 3.8
        assert preview["card_in_eur"] == 0.7
        assert preview["bank_transfer_in_eur"] == 4
        assert preview["total_inflow_eur"] == 8.5
        assert preview["total_refund_eur"] == 0
        assert preview["expected_cash_eur"] == 53.8
        assert preview["retail_sale_count"] == 2
        assert preview["payment_count"] == 1

        day_close = client.post(
            "/api/day-closes",
            json={
                "business_date": "2026-09-20",
                "opening_cash_eur": 50,
                "counted_cash_eur": 54,
                "notes": "Zaključek tržnice.",
            },
        )
        assert day_close.status_code == 201
        assert day_close.json()["expected_cash_eur"] == 53.8
        assert day_close.json()["counted_cash_eur"] == 54
        assert day_close.json()["difference_eur"] == 0.2
        assert client.post(
            "/api/day-closes",
            json={
                "business_date": "2026-09-20",
                "opening_cash_eur": 50,
                "counted_cash_eur": 54,
            },
        ).status_code == 409

        closed_preview = client.get(
            "/api/day-closes/preview?business_date=2026-09-20&opening_cash_eur=0"
        )
        assert closed_preview.status_code == 200
        assert closed_preview.json()["closed"] is True
        assert closed_preview.json()["opening_cash_eur"] == 50
        assert len(client.get("/api/day-closes").json()) == 1

        late_sale = client.post(
            "/api/retail-sales",
            json={
                "sale_date": "2026-09-20",
                "payment_method": "cash",
                "items": [
                    {
                        "harvest_id": second_quality_harvest.json()["id"],
                        "quantity_kg": 0.1,
                        "price_per_kg_eur": 5,
                    }
                ],
            },
        )
        assert late_sale.status_code == 409
        assert "že zaključen" in late_sale.json()["detail"]

        late_payment = client.post(
            f"/api/orders/{fulfilled_order.json()['id']}/payments",
            json={
                "payment_date": "2026-09-20",
                "amount_eur": 1,
                "payment_method": "cash",
            },
        )
        assert late_payment.status_code == 409
        assert "že zaključen" in late_payment.json()["detail"]

        refund_day_preview = client.get(
            "/api/day-closes/preview?business_date=2026-09-23&opening_cash_eur=20"
        )
        assert refund_day_preview.status_code == 200
        refund_preview = refund_day_preview.json()
        assert refund_preview["card_refund_eur"] == 0.7
        assert refund_preview["total_refund_eur"] == 0.7
        assert refund_preview["net_receipts_eur"] == -0.7
        assert refund_preview["expected_cash_eur"] == 20
        assert refund_preview["refund_count"] == 2

        refund_day_close = client.post(
            "/api/day-closes",
            json={
                "business_date": "2026-09-23",
                "opening_cash_eur": 20,
                "counted_cash_eur": 20,
            },
        )
        assert refund_day_close.status_code == 201
        assert refund_day_close.json()["difference_eur"] == 0

        late_refund = client.post(
            f"/api/credit-notes/{credit_note_data['id']}/refunds",
            json={
                "refund_date": "2026-09-23",
                "amount_eur": 0.01,
                "payment_method": "card",
            },
        )
        assert late_refund.status_code == 409
        assert "že zaključen" in late_refund.json()["detail"]
        assert len(client.get("/api/day-closes").json()) == 2

        supplier = client.post(
            "/api/suppliers",
            json={
                "name": "Agro oskrba",
                "tax_number": "SI12345678",
                "email": "narocila@example.test",
                "phone": "+386 1 555 01 01",
            },
        )
        assert supplier.status_code == 201
        assert supplier.json()["name"] == "Agro oskrba"
        assert client.post(
            "/api/suppliers",
            json={"name": "agro oskrba"},
        ).status_code == 409

        seed_supply = client.post(
            "/api/supply-items",
            json={
                "name": "Seme rukole Astro",
                "category": "seed",
                "unit": "vrečka",
                "opening_stock": 1,
                "reorder_level": 2,
            },
        )
        assert seed_supply.status_code == 201
        assert seed_supply.json()["low_stock"] is True
        packaging_supply = client.post(
            "/api/supply-items",
            json={
                "name": "Papirnata vrečka 1 kg",
                "category": "packaging",
                "unit": "kos",
                "reorder_level": 50,
            },
        )
        assert packaging_supply.status_code == 201

        invalid_purchase_date = client.post(
            "/api/purchase-orders",
            json={
                "supplier_id": supplier.json()["id"],
                "order_date": "2026-09-28",
                "expected_date": "2026-09-27",
                "payment_method": "bank_transfer",
                "items": [
                    {
                        "supply_item_id": seed_supply.json()["id"],
                        "quantity": 3,
                        "unit_price_eur": 4.5,
                    }
                ],
            },
        )
        assert invalid_purchase_date.status_code == 422

        purchase = client.post(
            "/api/purchase-orders",
            json={
                "supplier_id": supplier.json()["id"],
                "order_date": "2026-09-28",
                "expected_date": "2026-10-01",
                "payment_method": "bank_transfer",
                "notes": "Jesenska dopolnitev zaloge.",
                "items": [
                    {
                        "supply_item_id": seed_supply.json()["id"],
                        "quantity": 3,
                        "unit_price_eur": 4.5,
                    },
                    {
                        "supply_item_id": packaging_supply.json()["id"],
                        "quantity": 100,
                        "unit_price_eur": 0.12,
                    },
                ],
            },
        )
        assert purchase.status_code == 201
        purchase_data = purchase.json()
        assert purchase_data["number"] == "NB-2026-0001"
        assert purchase_data["status"] == "ordered"
        assert purchase_data["total_eur"] == 25.5
        assert len(purchase_data["items"]) == 2

        stock_before_receipt = client.get("/api/supply-items").json()
        seed_before = next(
            item for item in stock_before_receipt
            if item["id"] == seed_supply.json()["id"]
        )
        assert seed_before["stock_quantity"] == 1

        invalid_receipt = client.post(
            f"/api/purchase-orders/{purchase_data['id']}/receive",
            json={"received_on": "2026-09-27"},
        )
        assert invalid_receipt.status_code == 422
        receipt = client.post(
            f"/api/purchase-orders/{purchase_data['id']}/receive",
            json={"received_on": "2026-10-01"},
        )
        assert receipt.status_code == 200
        assert receipt.json()["status"] == "received"
        assert receipt.json()["received_on"] == "2026-10-01"
        assert client.post(
            f"/api/purchase-orders/{purchase_data['id']}/receive",
            json={"received_on": "2026-10-01"},
        ).status_code == 409

        stock_after_receipt = client.get("/api/supply-items").json()
        seed_after = next(
            item for item in stock_after_receipt
            if item["id"] == seed_supply.json()["id"]
        )
        packaging_after = next(
            item for item in stock_after_receipt
            if item["id"] == packaging_supply.json()["id"]
        )
        assert seed_after["stock_quantity"] == 4
        assert seed_after["low_stock"] is False
        assert packaging_after["stock_quantity"] == 100

        cancelled_purchase = client.post(
            "/api/purchase-orders",
            json={
                "supplier_id": supplier.json()["id"],
                "order_date": "2026-10-02",
                "payment_method": "card",
                "items": [
                    {
                        "supply_item_id": seed_supply.json()["id"],
                        "quantity": 1,
                        "unit_price_eur": 4.5,
                    }
                ],
            },
        )
        assert cancelled_purchase.status_code == 201
        cancelled = client.post(
            f"/api/purchase-orders/{cancelled_purchase.json()['id']}/cancel"
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert client.post(
            f"/api/purchase-orders/{cancelled_purchase.json()['id']}/receive",
            json={"received_on": "2026-10-03"},
        ).status_code == 409
        assert len(client.get("/api/purchase-orders").json()) == 2
        assert len(client.get("/api/suppliers").json()) == 1

        supply_usage = client.post(
            "/api/supply-usages",
            json={
                "supply_item_id": seed_supply.json()["id"],
                "bed_id": bed["id"],
                "planting_id": planting.json()["id"],
                "usage_date": "2026-10-02",
                "quantity": 1.5,
                "notes": "Jesenska setev.",
            },
        )
        assert supply_usage.status_code == 201
        usage_data = supply_usage.json()
        assert usage_data["unit_cost_eur"] == 4.5
        assert usage_data["total_cost_eur"] == 6.75
        assert usage_data["bed"] == bed["name"]
        assert client.post(
            "/api/supply-usages",
            json={
                "supply_item_id": seed_supply.json()["id"],
                "bed_id": bed["id"],
                "usage_date": "2026-10-02",
                "quantity": 99,
            },
        ).status_code == 409
        usage_stock = next(
            item for item in client.get("/api/supply-items").json()
            if item["id"] == seed_supply.json()["id"]
        )
        assert usage_stock["stock_quantity"] == 2.5
        assert len(client.get("/api/supply-usages").json()) == 1

        economics_after_usage = next(
            item for item in client.get("/api/economics/by-bed").json()
            if item["bed_id"] == bed["id"]
        )
        assert economics_after_usage["direct_costs_eur"] == 42.5
        assert economics_after_usage["material_costs_eur"] == 6.75
        assert economics_after_usage["labor_costs_eur"] == 5
        assert economics_after_usage["costs_eur"] == 54.25
        assert economics_after_usage["profit_eur"] == 54.25

        supplier_partial_payment = client.post(
            f"/api/purchase-orders/{purchase_data['id']}/payments",
            json={
                "payment_date": "2026-10-02",
                "amount_eur": 10,
                "payment_method": "cash",
                "notes": "Delno plačilo ob prevzemu.",
            },
        )
        assert supplier_partial_payment.status_code == 201
        assert supplier_partial_payment.json()["payment_status"] == "partial"
        assert supplier_partial_payment.json()["paid_eur"] == 10
        assert supplier_partial_payment.json()["outstanding_eur"] == 15.5
        assert len(supplier_partial_payment.json()["payments"]) == 1
        assert client.post(
            f"/api/purchase-orders/{purchase_data['id']}/payments",
            json={
                "payment_date": "2026-10-03",
                "amount_eur": 16,
                "payment_method": "bank_transfer",
            },
        ).status_code == 409

        supplier_close_preview = client.get(
            "/api/day-closes/preview?business_date=2026-10-02&opening_cash_eur=100"
        )
        assert supplier_close_preview.status_code == 200
        supplier_preview = supplier_close_preview.json()
        assert supplier_preview["cash_supplier_payment_eur"] == 10
        assert supplier_preview["total_supplier_payment_eur"] == 10
        assert supplier_preview["total_outflow_eur"] == 10
        assert supplier_preview["net_receipts_eur"] == -10
        assert supplier_preview["expected_cash_eur"] == 90
        assert supplier_preview["supplier_payment_count"] == 1

        supplier_day_close = client.post(
            "/api/day-closes",
            json={
                "business_date": "2026-10-02",
                "opening_cash_eur": 100,
                "counted_cash_eur": 90,
            },
        )
        assert supplier_day_close.status_code == 201
        assert supplier_day_close.json()["difference_eur"] == 0
        assert supplier_day_close.json()["cash_supplier_payment_eur"] == 10
        assert client.post(
            f"/api/purchase-orders/{purchase_data['id']}/payments",
            json={
                "payment_date": "2026-10-02",
                "amount_eur": 1,
                "payment_method": "cash",
            },
        ).status_code == 409

        supplier_final_payment = client.post(
            f"/api/purchase-orders/{purchase_data['id']}/payments",
            json={
                "payment_date": "2026-10-03",
                "amount_eur": 15.5,
                "payment_method": "bank_transfer",
            },
        )
        assert supplier_final_payment.status_code == 201
        assert supplier_final_payment.json()["payment_status"] == "paid"
        assert supplier_final_payment.json()["paid_eur"] == 25.5
        assert supplier_final_payment.json()["outstanding_eur"] == 0
        assert len(supplier_final_payment.json()["payments"]) == 2
        assert client.post(
            f"/api/purchase-orders/{cancelled_purchase.json()['id']}/payments",
            json={
                "payment_date": "2026-10-03",
                "amount_eur": 1,
                "payment_method": "card",
            },
        ).status_code == 409

        supplier_cash_flow = client.get(
            "/api/cash-flow?start=2026-10-02&end=2026-10-03"
        )
        assert supplier_cash_flow.status_code == 200
        supplier_flow = supplier_cash_flow.json()
        assert supplier_flow["summary"]["inflow_eur"] == 0
        assert supplier_flow["summary"]["outflow_eur"] == 25.5
        assert supplier_flow["summary"]["net_eur"] == -25.5
        assert supplier_flow["summary"]["supplier_payments_eur"] == 25.5
        assert supplier_flow["summary"]["supplier_payment_count"] == 2
        assert supplier_flow["summary"]["costs_by_category"] == {
            "purchasing": 25.5
        }
        assert len(supplier_flow["entries"]) == 2
        assert {entry["source"] for entry in supplier_flow["entries"]} == {
            "supplier_payment"
        }
        assert {entry["method"] for entry in supplier_flow["entries"]} == {
            "cash",
            "bank_transfer",
        }
        supplier_cash_flow_csv = client.get(
            "/api/cash-flow/export.csv?start=2026-10-02&end=2026-10-03"
        )
        assert supplier_cash_flow_csv.status_code == 200
        assert "Plačilo dobavitelju" in supplier_cash_flow_csv.text
        assert "Agro oskrba" in supplier_cash_flow_csv.text
        assert len(client.get("/api/day-closes").json()) == 3

        analytics_bed = client.post(
            "/api/beds",
            json={"name": "Z9", "width_m": 0.8, "length_m": 10},
        )
        assert analytics_bed.status_code == 201
        analytics_planting = client.post(
            "/api/plantings",
            json={
                "crop_id": crop["id"],
                "variety_id": variety["id"],
                "bed_id": analytics_bed.json()["id"],
                "sowing_date": "2027-01-01",
            },
        )
        assert analytics_planting.status_code == 201
        with SessionLocal() as db:
            stored_analytics_planting = db.get(
                Planting, analytics_planting.json()["id"]
            )
            stored_analytics_planting.expected_harvest_date = date(2027, 3, 20)
            first_growth_check = db.scalar(
                select(Task).where(
                    Task.planting_id == stored_analytics_planting.id,
                    Task.task_type == "growth_check",
                )
            )
            first_growth_check.status = "completed"
            first_growth_check.completed_at = datetime.now(timezone.utc)
            db.commit()
        growth_review = client.get(
            "/api/task-review?date=2027-02-04&horizon_days=2"
        )
        assert growth_review.status_code == 200
        recurring_growth = next(
            item
            for item in growth_review.json()["suggestions"]
            if item["planting_id"] == analytics_planting.json()["id"]
            and item["task_type"] == "growth_check"
        )
        assert recurring_growth["due_date"] == "2027-02-05"
        assert "14-dnevni" in recurring_growth["reason"]
        analytics_harvest = client.post(
            "/api/harvests",
            json={
                "planting_id": analytics_planting.json()["id"],
                "harvest_date": "2027-02-01",
                "quantity_kg": 10,
                "quality": "A",
            },
        )
        assert analytics_harvest.status_code == 201
        assert client.post(
            "/api/costs",
            json={
                "bed_id": analytics_bed.json()["id"],
                "planting_id": analytics_planting.json()["id"],
                "cost_date": "2027-02-01",
                "category": "other",
                "amount_eur": 10,
                "description": "Neposredni strošek setve",
            },
        ).status_code == 201
        assert client.post(
            "/api/costs",
            json={
                "bed_id": analytics_bed.json()["id"],
                "cost_date": "2027-02-01",
                "category": "other",
                "amount_eur": 5,
                "description": "Splošni strošek gredice",
            },
        ).status_code == 201
        analytics_usage = client.post(
            "/api/supply-usages",
            json={
                "supply_item_id": seed_supply.json()["id"],
                "bed_id": analytics_bed.json()["id"],
                "planting_id": analytics_planting.json()["id"],
                "usage_date": "2027-02-01",
                "quantity": 0.5,
            },
        )
        assert analytics_usage.status_code == 201
        assert analytics_usage.json()["total_cost_eur"] == 2.25
        analytics_labor = client.post(
            "/api/labor-entries",
            json={
                "worker_id": worker_data["id"],
                "bed_id": analytics_bed.json()["id"],
                "planting_id": analytics_planting.json()["id"],
                "work_date": "2027-02-01",
                "duration_minutes": 60,
                "description": "Žetev in priprava",
            },
        )
        assert analytics_labor.status_code == 201
        assert analytics_labor.json()["total_cost_eur"] == 12
        assert client.post(
            "/api/sales",
            json={
                "harvest_id": analytics_harvest.json()["id"],
                "sale_date": "2027-02-02",
                "quantity_kg": 6,
                "price_per_kg_eur": 8,
                "customer": "Tržnica",
            },
        ).status_code == 201
        analytics_order = client.post(
            "/api/orders",
            json={
                "customer_id": customer.json()["id"],
                "order_date": "2027-02-03",
                "delivery_date": "2027-02-03",
                "items": [
                    {
                        "harvest_id": analytics_harvest.json()["id"],
                        "quantity_kg": 2,
                        "price_per_kg_eur": 8,
                    }
                ],
            },
        )
        assert analytics_order.status_code == 201
        assert client.post(
            f"/api/orders/{analytics_order.json()['id']}/status",
            json={"status": "fulfilled"},
        ).status_code == 200
        analytics_invoice = client.post(
            "/api/invoices",
            json={
                "source_type": "order",
                "source_id": analytics_order.json()["id"],
                "issued_on": "2027-02-03",
                "payment_method": "bank_transfer",
            },
        )
        assert analytics_invoice.status_code == 201
        analytics_credit_note = client.post(
            f"/api/invoices/{analytics_invoice.json()['id']}/credit-notes",
            json={
                "issued_on": "2027-02-04",
                "reason": "Test sezonskega poročila",
            },
        )
        assert analytics_credit_note.status_code == 201
        assert analytics_credit_note.json()["total_eur"] == 16

        profitability = client.get(
            "/api/profitability-report?start=2027-01-01&end=2027-02-28"
        )
        assert profitability.status_code == 200
        profitability_data = profitability.json()
        assert profitability_data["summary"] == {
            "active_area_m2": 8,
            "harvested_kg": 10,
            "sold_kg": 8,
            "gross_revenue_eur": 64,
            "credit_notes_eur": 16,
            "net_revenue_eur": 48,
            "direct_costs_eur": 15,
            "overhead_costs_eur": 0,
            "material_costs_eur": 2.25,
            "labor_costs_eur": 12,
            "costs_eur": 29.25,
            "profit_eur": 18.75,
            "margin_pct": 39.06,
            "labor_hours": 1,
            "harvest_kg_m2": 1.25,
            "revenue_eur_m2": 6,
            "profit_eur_m2": 2.34,
            "profit_eur_per_labor_hour": 18.75,
            "unallocated_direct_costs_eur": 5,
            "unallocated_material_costs_eur": 0,
            "unallocated_labor_costs_eur": 0,
            "unallocated_overhead_costs_eur": 0,
            "unallocated_costs_eur": 5,
            "unallocated_credit_notes_eur": 0,
        }
        assert profitability_data["range"] == {
            "start": "2027-01-01",
            "end": "2027-02-28",
        }
        assert len(profitability_data["by_bed"]) == 1
        bed_profitability = profitability_data["by_bed"][0]
        assert bed_profitability["bed"] == "Z9"
        assert bed_profitability["net_revenue_eur"] == 48
        assert bed_profitability["costs_eur"] == 29.25
        assert bed_profitability["profit_eur"] == 18.75
        assert bed_profitability["crops"] == ["Rukola"]
        assert len(profitability_data["by_crop"]) == 1
        crop_profitability = profitability_data["by_crop"][0]
        assert crop_profitability["crop"] == "Rukola"
        assert crop_profitability["net_revenue_eur"] == 48
        assert crop_profitability["costs_eur"] == 24.25
        assert crop_profitability["profit_eur"] == 23.75
        assert crop_profitability["margin_pct"] == 49.48
        assert crop_profitability["profit_eur_m2"] == 2.97
        assert crop_profitability["profit_eur_per_labor_hour"] == 23.75
        profitability_csv = client.get(
            "/api/profitability-report/export.csv?start=2027-01-01&end=2027-02-28"
        )
        assert profitability_csv.status_code == 200
        assert "Gredica;Z9" in profitability_csv.text
        assert "Kultura;Rukola" in profitability_csv.text
        assert client.get(
            "/api/profitability-report?start=2027-03-01&end=2027-02-28"
        ).status_code == 422

        fuel_expense = client.post(
            "/api/farm-expenses",
            json={
                "expense_date": "2027-03-01",
                "category": "fuel",
                "amount_eur": 30,
                "payment_method": "cash",
                "supplier": "Bencinski servis",
                "reference": "RAC-2027-15",
                "description": "Gorivo za dostavo",
            },
        )
        assert fuel_expense.status_code == 201
        assert fuel_expense.json()["amount_eur"] == 30
        assert fuel_expense.json()["category"] == "fuel"

        utilities_expense = client.post(
            "/api/farm-expenses",
            json={
                "expense_date": "2027-03-01",
                "category": "utilities",
                "amount_eur": 20,
                "payment_method": "card",
                "supplier": "Elektro",
                "description": "Elektrika rastlinjaka",
            },
        )
        assert utilities_expense.status_code == 201

        expenses = client.get(
            "/api/farm-expenses?start=2027-03-01&end=2027-03-31"
        )
        assert expenses.status_code == 200
        assert len(expenses.json()) == 2
        assert sum(item["amount_eur"] for item in expenses.json()) == 50
        assert client.post(
            "/api/farm-expenses",
            json={
                "expense_date": "2027-03-02",
                "category": "other",
                "amount_eur": 1,
                "payment_method": "cash",
                "description": "   ",
            },
        ).status_code == 422

        farm_profitability = client.get(
            "/api/profitability-report?start=2027-03-01&end=2027-03-31"
        )
        assert farm_profitability.status_code == 200
        farm_summary = farm_profitability.json()["summary"]
        assert farm_summary["overhead_costs_eur"] == 50
        assert farm_summary["costs_eur"] == 50
        assert farm_summary["profit_eur"] == -50
        assert farm_summary["unallocated_overhead_costs_eur"] == 50
        assert farm_summary["unallocated_costs_eur"] == 50
        assert farm_profitability.json()["by_bed"] == []
        assert farm_profitability.json()["by_crop"] == []

        farm_cash_flow = client.get(
            "/api/cash-flow?start=2027-03-01&end=2027-03-31"
        )
        assert farm_cash_flow.status_code == 200
        farm_cash_flow_data = farm_cash_flow.json()
        assert farm_cash_flow_data["summary"]["outflow_eur"] == 50
        assert farm_cash_flow_data["summary"]["net_eur"] == -50
        assert farm_cash_flow_data["summary"]["outflow_count"] == 2
        assert farm_cash_flow_data["summary"]["costs_by_category"] == {
            "fuel": 30,
            "utilities": 20,
        }
        assert {entry["source"] for entry in farm_cash_flow_data["entries"]} == {
            "farm_expense"
        }

        farm_day_preview = client.get(
            "/api/day-closes/preview?business_date=2027-03-01&opening_cash_eur=100"
        )
        assert farm_day_preview.status_code == 200
        farm_day_preview_data = farm_day_preview.json()
        assert farm_day_preview_data["cash_farm_expense_eur"] == 30
        assert farm_day_preview_data["card_farm_expense_eur"] == 20
        assert farm_day_preview_data["total_farm_expense_eur"] == 50
        assert farm_day_preview_data["farm_expense_count"] == 2
        assert farm_day_preview_data["total_outflow_eur"] == 50
        assert farm_day_preview_data["net_receipts_eur"] == -50
        assert farm_day_preview_data["expected_cash_eur"] == 70

        farm_day_close = client.post(
            "/api/day-closes",
            json={
                "business_date": "2027-03-01",
                "opening_cash_eur": 100,
                "counted_cash_eur": 70,
                "note": "Splošni stroški preverjeni",
            },
        )
        assert farm_day_close.status_code == 201
        farm_day_close_data = farm_day_close.json()
        assert farm_day_close_data["cash_farm_expense_eur"] == 30
        assert farm_day_close_data["total_farm_expense_eur"] == 50
        assert farm_day_close_data["difference_eur"] == 0
        assert client.post(
            "/api/farm-expenses",
            json={
                "expense_date": "2027-03-01",
                "category": "other",
                "amount_eur": 5,
                "payment_method": "cash",
                "description": "Prepozen vnos",
            },
        ).status_code == 409

        farm_cash_flow_csv = client.get(
            "/api/cash-flow/export.csv?start=2027-03-01&end=2027-03-31"
        )
        assert farm_cash_flow_csv.status_code == 200
        assert "Gorivo za dostavo" in farm_cash_flow_csv.text
        assert "Bencinski servis" in farm_cash_flow_csv.text
        farm_profitability_csv = client.get(
            "/api/profitability-report/export.csv?start=2027-03-01&end=2027-03-31"
        )
        assert farm_profitability_csv.status_code == 200
        assert "Splošni stroški EUR" in farm_profitability_csv.text
        assert "Skupaj;Kmetija" in farm_profitability_csv.text

        data_safety = client.get("/api/system/data-safety")
        assert data_safety.status_code == 200
        data_safety_summary = data_safety.json()
        assert data_safety_summary["schema_revision"] == "0008_green_chilli_harvest"
        assert data_safety_summary["backup_format_version"] == 1
        assert data_safety_summary["storage_location"] is None
        assert data_safety_summary["storage_move_supported"] is False
        assert data_safety_summary["table_count"] == 37
        assert data_safety_summary["record_count"] > 0
        assert data_safety_summary["daily_backup_retention"] == 14
        assert len(data_safety_summary["daily_backups"]) == 1
        assert data_safety_summary["automatic_backups"] == []

        os.environ["GROWMASTER_DATA_ROOT"] = "D:/GrowMasterData"
        os.environ["GROWMASTER_WINDOWS_INSTALL"] = "true"
        try:
            windows_storage = client.get("/api/system/data-safety").json()
            assert windows_storage["storage_location"] == "D:/GrowMasterData"
            assert windows_storage["storage_move_supported"] is True
        finally:
            os.environ.pop("GROWMASTER_DATA_ROOT", None)
            os.environ.pop("GROWMASTER_WINDOWS_INSTALL", None)

        production_readiness = client.get("/api/system/readiness")
        assert production_readiness.status_code == 200
        assert production_readiness.json()["version"] == "1.22.1"
        assert production_readiness.json()["operational_ready"] is True
        assert production_readiness.json()["business_documents_ready"] is True
        assert all(
            item["status"] == "ready"
            for item in production_readiness.json()["checks"]
        )

        daily_filename = data_safety_summary["daily_backups"][0]["filename"]
        assert daily_filename.startswith("growmaster-daily-")
        with SessionLocal() as db:
            assert ensure_daily_backup(db) == daily_filename
        assert len(list_daily_backups()) == 1
        daily_backup = client.get(
            f"/api/system/backups/daily/{daily_filename}"
        )
        assert daily_backup.status_code == 200
        daily_document = daily_backup.json()
        daily_farms = daily_document["payload"]["tables"]["farms"]
        assert daily_farms[0]["name"] == "Testna kmetija"
        assert "admin_credentials" not in daily_document["payload"]["tables"]
        assert client.get(
            "/api/system/backups/daily/not-a-backup.json"
        ).status_code == 404

        (TEST_BACKUP_DIRECTORY / daily_filename).write_bytes(b"damaged")
        damaged_readiness = client.get("/api/system/readiness").json()
        damaged_checks = {
            item["key"]: item["status"]
            for item in damaged_readiness["checks"]
        }
        assert damaged_readiness["operational_ready"] is False
        assert damaged_checks["daily_backup"] == "blocked"
        with SessionLocal() as db:
            refresh_daily_backup(db)
        repaired_readiness = client.get("/api/system/readiness").json()
        assert repaired_readiness["operational_ready"] is True

        portable_backup = client.get("/api/system/backups/export")
        assert portable_backup.status_code == 200
        assert portable_backup.headers["content-type"].startswith("application/json")
        assert "growmaster-backup-" in portable_backup.headers[
            "content-disposition"
        ]
        backup_document = portable_backup.json()
        assert len(backup_document["checksum_sha256"]) == 64
        assert portable_backup.headers["x-growmaster-checksum-sha256"] == (
            backup_document["checksum_sha256"]
        )
        assert backup_document["payload"]["record_count"] == (
            data_safety_summary["record_count"]
        )
        assert backup_document["payload"]["schema_revision"] == "0001_current_schema"
        assert len(backup_document["payload"]["tables"]) == 37
        assert "admin_credentials" not in backup_document["payload"]["tables"]
        assert "auth_sessions" not in backup_document["payload"]["tables"]
        backup_variety = backup_document["payload"]["tables"]["varieties"][0]
        assert {
            "days_spring",
            "days_summer",
            "days_autumn",
            "days_winter",
        } <= set(backup_variety)
        assert "composition" in backup_variety

        metadata_fields = {
            "source_name",
            "source_url",
            "seed_forms",
            "traits",
            "slovenia_note",
            "days_baby",
            "seed_rate_g_m2",
            "seed_spacing_cm",
            "row_spacing_cm",
            "planting_method",
            "outdoor_months",
            "protected_months",
            "heat_tolerance",
            "cold_tolerance",
            "planting_calendar_note",
            "succession_interval_days",
            "calendar_source_url",
            "cultivation_methods",
            "harvest_methods",
            "nursery_days",
            "direct_sow_extra_days",
            "days_outer_leaf",
            "regrowth_interval_min_days",
            "regrowth_interval_max_days",
            "max_regrowth_cuts",
            "days_green_harvest",
            "harvest_interval_days",
            "harvest_duration_days",
            "harvest_profile_note",
            "harvest_source_url",
        }
        assert metadata_fields <= set(backup_variety)

        premetadata_document = json.loads(portable_backup.content)
        for row in premetadata_document["payload"]["tables"]["varieties"]:
            for field in metadata_fields:
                row.pop(field)
        premetadata_document["checksum_sha256"] = hashlib.sha256(
            canonical_json(premetadata_document["payload"])
        ).hexdigest()
        parsed_premetadata = parse_backup(
            json.dumps(premetadata_document, ensure_ascii=False).encode("utf-8")
        )
        assert all(
            parsed_premetadata.rows_by_table["varieties"][0][field] is None
            for field in metadata_fields
        )

        precomposition_document = json.loads(json.dumps(premetadata_document))
        for row in precomposition_document["payload"]["tables"]["varieties"]:
            row.pop("composition")
        precomposition_document["checksum_sha256"] = hashlib.sha256(
            canonical_json(precomposition_document["payload"])
        ).hexdigest()
        parsed_precomposition = parse_backup(
            json.dumps(precomposition_document, ensure_ascii=False).encode("utf-8")
        )
        assert parsed_precomposition.rows_by_table["varieties"][0][
            "composition"
        ] is None

        legacy_document = json.loads(json.dumps(precomposition_document))
        for row in legacy_document["payload"]["tables"]["varieties"]:
            for field in (
                "days_spring",
                "days_summer",
                "days_autumn",
                "days_winter",
            ):
                row.pop(field)
        legacy_document["checksum_sha256"] = hashlib.sha256(
            canonical_json(legacy_document["payload"])
        ).hexdigest()
        parsed_legacy = parse_backup(
            json.dumps(legacy_document, ensure_ascii=False).encode("utf-8")
        )
        assert parsed_legacy.rows_by_table["varieties"][0]["days_winter"] > 0

        assert client.post(
            "/api/system/backups/restore?confirmation=NAPAČNO",
            content=portable_backup.content,
            headers={"Content-Type": "application/json"},
        ).status_code == 422
        tampered_backup = portable_backup.json()
        tampered_backup["payload"]["record_count"] += 1
        assert client.post(
            "/api/system/backups/restore?confirmation=OBNOVI",
            json=tampered_backup,
        ).status_code == 422

        beds_before_restore = client.get("/api/beds").json()
        temporary_bed = client.post(
            "/api/beds",
            json={"name": "ZAČASNA", "width_m": 1, "length_m": 3},
        )
        assert temporary_bed.status_code == 201
        assert len(client.get("/api/beds").json()) == len(beds_before_restore) + 1

        restored = client.post(
            "/api/system/backups/restore?confirmation=OBNOVI",
            content=portable_backup.content,
            headers={"Content-Type": "application/json"},
        )
        assert restored.status_code == 200
        restored_data = restored.json()
        assert restored_data["restored_records"] == data_safety_summary["record_count"]
        assert restored_data["safety_backup"].startswith("growmaster-auto-")
        beds_after_restore = client.get("/api/beds").json()
        assert len(beds_after_restore) == len(beds_before_restore)
        assert all(item["name"] != "ZAČASNA" for item in beds_after_restore)

        safety_after_restore = client.get("/api/system/data-safety").json()
        assert len(safety_after_restore["automatic_backups"]) == 1
        automatic_filename = safety_after_restore["automatic_backups"][0][
            "filename"
        ]
        automatic_backup = client.get(
            f"/api/system/backups/automatic/{automatic_filename}"
        )
        assert automatic_backup.status_code == 200
        automatic_beds = automatic_backup.json()["payload"]["tables"]["beds"]
        assert any(item["name"] == "ZAČASNA" for item in automatic_beds)
        assert client.get(
            "/api/system/backups/automatic/not-a-backup.json"
        ).status_code == 404

        bed_after_restore = client.post(
            "/api/beds",
            json={"name": "PO-OBNOVI", "width_m": 1, "length_m": 4},
        )
        assert bed_after_restore.status_code == 201
        assert bed_after_restore.json()["id"] > max(
            item["id"] for item in beds_after_restore
        )

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200
        assert client.get("/api/beds").status_code == 401
        assert client.post(
            "/api/auth/login", json={"password": "Napačno geslo 2026!"}
        ).status_code == 401
        login = client.post(
            "/api/auth/login", json={"password": "Zelo varno geslo 2026!"}
        )
        assert login.status_code == 200
        assert login.json()["display_name"] == "Nosilec kmetije"
        assert client.get("/api/beds").status_code == 200

        account = client.get("/api/auth/account")
        assert account.status_code == 200
        assert account.json()["display_name"] == "Nosilec kmetije"
        assert account.json()["active_sessions"] == 1
        assert client.put(
            "/api/auth/account",
            json={
                "display_name": "Vodja kmetije",
                "current_password": "Napačno geslo 2026!",
            },
        ).status_code == 401
        renamed = client.put(
            "/api/auth/account",
            json={
                "display_name": "  Vodja kmetije  ",
                "current_password": "Zelo varno geslo 2026!",
            },
        )
        assert renamed.status_code == 200
        assert renamed.json()["display_name"] == "Vodja kmetije"
        first_session_token = client.cookies.get("growmaster_session")

        second_login = client.post(
            "/api/auth/login", json={"password": "Zelo varno geslo 2026!"}
        )
        assert second_login.status_code == 200
        assert client.get("/api/auth/account").json()["active_sessions"] == 2
        assert client.post(
            "/api/auth/change-password",
            json={
                "current_password": "Zelo varno geslo 2026!",
                "new_password": "Zelo varno geslo 2026!",
            },
        ).status_code == 422
        changed_password = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "Zelo varno geslo 2026!",
                "new_password": "Novo varno geslo 2027!",
            },
        )
        assert changed_password.status_code == 200
        assert changed_password.json()["active_sessions"] == 1
        replacement_token = client.cookies.get("growmaster_session")
        assert replacement_token != first_session_token

        client.cookies.clear()
        client.cookies.set("growmaster_session", first_session_token)
        assert client.get("/api/beds").status_code == 401
        client.cookies.clear()
        client.cookies.set("growmaster_session", replacement_token)
        assert client.get("/api/beds").status_code == 200

        assert client.post("/api/auth/logout").status_code == 200
        assert client.post(
            "/api/auth/login", json={"password": "Zelo varno geslo 2026!"}
        ).status_code == 401
        new_login = client.post(
            "/api/auth/login", json={"password": "Novo varno geslo 2027!"}
        )
        assert new_login.status_code == 200
        assert new_login.json()["display_name"] == "Vodja kmetije"
        assert "session_token" not in new_login.json()

        with TestClient(app) as mobile_client:
            mobile_login = mobile_client.post(
                "/api/auth/login",
                json={"password": "Novo varno geslo 2027!"},
                headers={
                    "X-GrowMaster-Client": "mobile",
                    "Origin": "capacitor://localhost",
                },
            )
            assert mobile_login.status_code == 200
            mobile_token = mobile_login.json()["session_token"]
            assert len(mobile_token) >= 32
            mobile_client.cookies.clear()
            mobile_headers = {
                "Authorization": f"Bearer {mobile_token}",
                "X-GrowMaster-Client": "mobile",
                "Origin": "capacitor://localhost",
            }
            mobile_beds = mobile_client.get("/api/beds", headers=mobile_headers)
            assert mobile_beds.status_code == 200
            assert mobile_beds.headers["access-control-allow-origin"] == (
                "capacitor://localhost"
            )
            assert mobile_client.get("/api/auth/status", headers=mobile_headers).json()[
                "authenticated"
            ] is True
            assert mobile_client.post("/api/auth/logout", headers=mobile_headers).status_code == 200
            assert mobile_client.get("/api/beds", headers=mobile_headers).status_code == 401

        with SessionLocal() as db:
            for day in range(1, 16):
                refresh_daily_backup(
                    db,
                    datetime(2099, 1, day, tzinfo=timezone.utc),
                )
        retained_daily = list_daily_backups()
        assert len(retained_daily) == 14
        assert retained_daily[0]["backup_date"] == "2099-01-15"
        assert retained_daily[-1]["backup_date"] == "2099-01-02"
