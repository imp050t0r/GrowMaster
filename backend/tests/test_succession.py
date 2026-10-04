from datetime import date, timedelta
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dynamic_dtm import store_prediction
from app.migrations import add_bed_release_date
from app.models import Bed, Crop, CropPlan, Farm, Planting, Variety
from app.succession import review
from app.successor_routes import router, succession_state

TODAY = date.today()


def test_harvest_comparison_route_scopes_farm_and_never_writes(setup):
    db, _, _, planting, _, client = setup
    current = planting()
    completed = planting(); completed.status = "completed"
    cancelled = planting(); cancelled.status = "cancelled"
    other = planting(); other.farm_id = 2
    db.commit()
    response = client.get("/api/planning/harvest-comparison")
    assert response.status_code == 200
    report = response.json()
    assert {r["planting_id"] for r in report["rows"]} == {current.id, completed.id}
    assert report["summary"]["eligible"] == 0
    assert not db.dirty and not db.new


def test_workload_route_scopes_farm_and_filters_plan_status(setup):
    from app.models import Task
    db, beds, _, _, plan, client=setup
    current=plan(start=12,nursery=7)
    cancelled=plan(start=12); cancelled.status="cancelled"
    other=plan(start=12); other.farm_id=2
    db.add_all([Task(farm_id=1,bed_id=beds[0].id,title="Test task",due_date=day(6),status="planned"),
                Task(farm_id=2,bed_id=beds[0].id,title="Other farm",due_date=day(6),status="planned"),
                Task(farm_id=1,bed_id=beds[0].id,title="Finished",due_date=day(6),status="completed")])
    db.commit()
    response=client.get(f'/api/planning/workload?start={day(0)}&end={day(60)}')
    assert response.status_code==200
    report=response.json()
    assert report['activity_count']==4
    assert sum(w['counts']['task'] for w in report['weeks'])==1
    assert not db.dirty and not db.new
    assert {r['plan_id'] for w in report['weeks'] for r in w['activities'] if 'plan_id' in r}=={current.id}


def test_workload_rejects_invalid_range(setup):
    client=setup[-1]
    assert client.get(f'/api/planning/workload?start={day(1)}&end={day(0)}').status_code==422
    assert client.get(f'/api/planning/workload?start={day(0)}&end={day(400)}').status_code==422


def day(offset):
    return TODAY + timedelta(days=offset)


@pytest.fixture
def setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        farm = Farm(id=1, name="Succession test")
        crop = Crop(name="Test crop", family="Testaceae", category="Domača")
        db.add_all([farm, crop]); db.flush()
        variety = Variety(crop_id=crop.id, name="Test cultivar", days_to_harvest=30,
                          days_spring=30, days_summer=30, days_autumn=30, days_winter=30,
                          harvest_methods="full_size")
        beds = [Bed(farm_id=1, name=f"S{i}", width_m=.8, length_m=15, status="empty") for i in range(3)]
        db.add_all([variety, *beds]); db.flush()
        def planting(end=20, **kwargs):
            item = Planting(farm_id=1, bed_id=beds[0].id, crop_id=crop.id, variety_id=variety.id,
                            sowing_date=day(-10), expected_harvest_date=day(10),
                            predicted_harvest_end=day(end), status="active", **kwargs)
            db.add(item); beds[0].status="growing"; db.flush()
            return item
        def plan(start=12, nursery=0, bed=0, **kwargs):
            item = CropPlan(farm_id=1, bed_id=beds[bed].id, crop_id=crop.id, variety_id=variety.id,
                            series_id="test", sowing_date=day(start-nursery),
                            transplant_date=day(start) if nursery else None,
                            expected_harvest_date=day(start+30), expected_yield_kg=10,
                            status="planned", **kwargs)
            db.add(item); db.flush()
            return item
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[get_db] = lambda: db
        yield db, beds, variety, planting, plan, TestClient(app)
    engine.dispose()


def test_delayed_harvest_cascades_and_preserves_nursery(setup):
    db, beds, _, planting, plan, _ = setup
    planting(); first=plan(nursery=7); second=plan(start=45)
    report=succession_state(db)[3]; group=report["beds"][0]
    a,b=group["plans"]
    assert group["can_apply"] is True
    assert a["shift_days"] == 9
    assert a["proposed"]["transplant_date"] == day(21)
    assert a["proposed"]["transplant_date"] - a["proposed"]["sowing_date"] == timedelta(days=7)
    assert b["proposed"]["sowing_date"] > a["occupied_through"]
    assert first.sowing_date == day(5) and second.sowing_date == day(45)


def test_same_day_release_requires_next_day(setup):
    db, _, _, planting, plan, _=setup
    planting(expected_bed_release_date=day(12)); plan()
    assert succession_state(db)[3]["beds"][0]["plans"][0]["shift_days"] == 1


def test_repeated_harvest_requires_explicit_release(setup):
    db, _, variety, planting, plan, _=setup
    variety.harvest_methods="full_size,cut_and_regrow"
    active=planting(); plan()
    report=succession_state(db)[3]
    assert report["beds"][0]["plans"][0]["blocked"]
    assert not report["beds"][0]["can_apply"]
    active.expected_bed_release_date=day(22)
    assert not succession_state(db)[3]["beds"][0]["plans"][0]["blocked"]


def test_overdue_active_cycle_cannot_be_assumed_finished(setup):
    db, _, _, planting, plan, _=setup
    active=planting(end=-1); active.expected_harvest_date=day(-2); plan()
    group=succession_state(db)[3]["beds"][0]
    assert group["active"][0]["basis"] == "active_overdue"
    assert group["plans"][0]["blocked"]


def test_past_sowing_prevents_batch_shift(setup):
    db, _, _, planting, plan, _=setup
    planting(); plan(nursery=20)
    group=succession_state(db)[3]["beds"][0]
    assert group["change_count"] == 1
    assert not group["can_apply"]


def test_alternatives_obey_dimensions_rotation_and_existing_plans(setup):
    db,beds,_,planting,plan,_=setup
    planting(); plan()
    def alternatives():
        return succession_state(db)[3]["beds"][0]["plans"][0]["alternative_beds"]
    assert {x["id"] for x in alternatives()} == {beds[1].id,beds[2].id}
    beds[1].last_crop_family="Testaceae"; beds[2].width_m=1
    assert alternatives() == []
    beds[1].last_crop_family=None; plan(start=200,bed=1)
    assert alternatives() == []


def test_apply_is_atomic_and_preserves_initial_dtm_snapshot(setup):
    db, beds, variety, planting, plan, client=setup
    active=planting(); first=plan(nursery=7); second=plan(start=45)
    store_prediction(first,variety); initial=first.dynamic_dtm_initial_snapshot
    db.commit()
    report=client.get('/api/planning/successions').json()
    response=client.post(f'/api/planning/successions/{beds[0].id}/apply',json={"token":report["token"]})
    assert response.status_code == 200, response.text
    assert len(response.json()["changes"]) == 2
    assert first.transplant_date == day(21)
    assert first.dynamic_dtm_initial_snapshot == initial
    assert json.loads(first.dynamic_dtm_explanation)["reference_date"] == day(21).isoformat()
    assert active.sowing_date == day(-10)
    assert client.post(f'/api/planning/successions/{beds[0].id}/apply',json={"token":report["token"]}).status_code == 409
    fresh=client.get('/api/planning/successions').json()
    assert fresh["beds"][0]["change_count"] == 0


def test_stale_dtm_rejects_action_without_changing_dates(setup):
    db,beds,_,planting,plan,client=setup
    active=planting(); planned=plan(); db.commit()
    token=client.get('/api/planning/successions').json()["token"]
    active.predicted_harvest_end=day(29); db.commit()
    assert client.post(f'/api/planning/successions/{beds[0].id}/apply',json={"token":token}).status_code == 409
    assert planned.sowing_date == day(12)


def test_release_update_validates_date_and_rejects_closed_record(setup):
    db,_,_,planting,plan,client=setup
    active=planting(); planned=plan(); db.commit()
    token=client.get('/api/planning/successions').json()["token"]
    path=f'/api/planning/successions/plantings/{active.id}/release'
    assert client.put(path,json={"token":token,"expected_bed_release_date":day(-1).isoformat()}).status_code == 422
    response=client.put(path,json={"token":token,"expected_bed_release_date":day(35).isoformat()})
    assert response.status_code == 200
    assert active.expected_bed_release_date == day(35)
    active.status='completed'; db.commit()
    token=client.get('/api/planning/successions').json()["token"]
    assert client.put(path,json={"token":token,"expected_bed_release_date":None}).status_code == 404


def test_move_rechecks_available_bed_and_preserves_dates(setup):
    db,beds,_,planting,plan,client=setup
    planting(); planned=plan(); db.commit()
    token=client.get('/api/planning/successions').json()["token"]
    path=f'/api/planning/successions/plans/{planned.id}/move'
    assert client.post(path,json={"token":token,"bed_id":99999}).status_code == 409
    assert client.post(path,json={"token":token,"bed_id":beds[1].id}).status_code == 200
    assert planned.bed_id == beds[1].id
    assert planned.sowing_date == day(12)


def test_cancelled_plans_and_other_farms_are_excluded(setup):
    db,_,_,planting,plan,_=setup
    planting(); cancelled=plan(); cancelled.status='cancelled'
    other=plan(start=10); other.farm_id=2; db.flush()
    report=succession_state(db)[3]
    assert report['beds'][0]['plans'] == []


def test_release_migration_preserves_old_values():
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        for table in ('plantings','crop_plans'):
            connection.execute(text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, expected_harvest_date DATE)'))
            connection.execute(text(f"INSERT INTO {table} VALUES (1, '2026-10-01')"))
        add_bed_release_date(connection); add_bed_release_date(connection)
        for table in ('plantings','crop_plans'):
            row=connection.execute(text(f'SELECT * FROM {table}')).mappings().one()
            assert row['expected_harvest_date'] == '2026-10-01'
            assert row['expected_bed_release_date'] is None
