from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import activate_crop_plan, finish_planting, planning_calendar
from app.models import Bed, Crop, CropPlan, Farm, Planting, Variety
from app.schemas import CropPlanActivate


HARVEST = date(2026, 6, 15)


@pytest.fixture
def calendar():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        db.add_all([Farm(id=1, name="Test"), Farm(id=2, name="Other")])
        db.add(Crop(id=1, name="Solata", family="Asteraceae", category="leafy"))
        db.flush()
        db.add(Variety(id=1, crop_id=1, name="Test", days_to_harvest=30,
                       days_spring=30, days_summer=30, days_autumn=30, days_winter=30))
        db.add_all([
            Bed(id=1, farm_id=1, name="A1", width_m=1, length_m=10, status="empty"),
            Bed(id=2, farm_id=2, name="B1", width_m=1, length_m=10, status="empty"),
        ])
        db.commit()
        app = FastAPI()
        app.get("/api/planning/calendar")(planning_calendar)
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            yield db, client
    engine.dispose()


def harvest_events(client, start=HARVEST, end=HARVEST):
    response = client.get("/api/planning/calendar", params={"start": str(start), "end": str(end)})
    assert response.status_code == 200
    return [event for event in response.json()["events"] if event["type"] == "planned_harvest"]


def test_harvest_survives_activation_once_and_disappears_on_completion(calendar):
    db, client = calendar
    plan = CropPlan(farm_id=1, bed_id=1, crop_id=1, variety_id=1, series_id="test",
                    sowing_date=HARVEST - timedelta(days=30),
                    expected_harvest_date=HARVEST, expected_yield_kg=10, status="planned")
    db.add(plan)
    db.commit()
    before = harvest_events(client)
    assert len(before) == 1 and before[0]["plan_id"] == plan.id

    result = activate_crop_plan(plan.id, CropPlanActivate(), db)
    after = harvest_events(client)
    assert after == [{"date": str(HARVEST), "type": "planned_harvest",
                      "title": "Predvidena žetev: Solata Test", "bed": "A1",
                      "planting_id": result["planting_id"]}]
    finish_planting(result["planting_id"], db)
    assert harvest_events(client) == []


@pytest.mark.parametrize("offset, included", [(-1, False), (0, True), (1, True), (2, False)])
def test_direct_planting_harvest_range_is_inclusive(calendar, offset, included):
    db, client = calendar
    planting = Planting(farm_id=1, bed_id=1, crop_id=1, variety_id=1,
                        sowing_date=HARVEST - timedelta(days=30),
                        expected_harvest_date=HARVEST + timedelta(days=offset), status="active")
    db.add(planting)
    db.commit()
    events = harvest_events(client, HARVEST, HARVEST + timedelta(days=1))
    assert [event["planting_id"] for event in events] == ([planting.id] if included else [])


def test_completed_and_other_farm_plantings_are_excluded(calendar):
    db, client = calendar
    for farm_id, bed_id, state in [(1, 1, "completed"), (2, 2, "active")]:
        db.add(Planting(farm_id=farm_id, bed_id=bed_id, crop_id=1, variety_id=1,
                        sowing_date=HARVEST - timedelta(days=30),
                        expected_harvest_date=HARVEST, status=state))
    db.commit()
    assert harvest_events(client) == []
