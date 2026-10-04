from datetime import date, timedelta
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.backups import create_backup_bytes, parse_backup, restore_parsed_backup
from app.database import Base, get_db
from app.dynamic_dtm import store_prediction
from app.dtm_learning import suggestion
from app.maturity import season_for_date
from app.models import Bed, Crop, CropPlan, Farm, Harvest, Planting, Variety
from app.successor_routes import router


@pytest.fixture
def learning():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        today = date.today()
        # Pick a future date safely inside its season, with last year's samples.
        reference = date(today.year + 1, 5, 15)
        farm = Farm(id=1, name="Learning test")
        crop = Crop(name="Test crop", family="Testaceae", category="Domača")
        db.add_all([farm, crop]); db.flush()
        variety = Variety(crop_id=crop.id, name="Test cultivar", days_to_harvest=30,
                          days_spring=30, days_summer=30, days_autumn=30, days_winter=30,
                          harvest_methods="full_size")
        bed = Bed(farm_id=1, name="17", width_m=.8, length_m=15, status="empty")
        db.add_all([variety, bed]); db.flush()
        plan = CropPlan(farm_id=1, bed_id=bed.id, crop_id=crop.id, variety_id=variety.id,
                        series_id="learning-test", sowing_date=reference,
                        expected_harvest_date=reference + timedelta(days=30),
                        expected_yield_kg=10, status="planned")
        store_prediction(plan, variety); db.add(plan)
        history = []
        for index, error in enumerate((3, 4, 5)):
            start = date(today.year - 1, 5, 1) + timedelta(days=index * 7)
            first = start + timedelta(days=30 + error)
            item = Planting(farm_id=1, bed_id=bed.id, crop_id=crop.id, variety_id=variety.id,
                            sowing_date=start, expected_harvest_date=start+timedelta(days=30),
                            completed_on=first+timedelta(days=1), status="completed")
            result = store_prediction(item, variety)
            result["calculated_at"] = f"{start.isoformat()}T00:00:00+00:00"
            item.dynamic_dtm_initial_snapshot = json.dumps(result)
            item.dynamic_dtm_explanation = item.dynamic_dtm_initial_snapshot
            db.add(item); db.flush()
            item.harvests.append(Harvest(farm_id=1, bed_id=bed.id, harvest_date=first,
                                         quantity_kg=3, quality="A"))
            history.append(item)
        db.commit()
        app=FastAPI(); app.include_router(router)
        app.dependency_overrides[get_db]=lambda: db
        yield db, plan, history, TestClient(app)
    engine.dispose()


def test_median_suggestion_does_not_write(learning):
    db, plan, history, _ = learning
    row=suggestion(plan, history)
    assert row["can_apply"] and row["correction_days"] == 4
    assert row["before_days"] == 30 and row["after_days"] == 34
    assert row["distinct_dates"] == 3
    assert not db.dirty and not db.new


def test_same_sowing_dates_are_not_independent_samples(learning):
    _, plan, history, _=learning
    for item in history[1:]:
        item.sowing_date=history[0].sowing_date
        item.dynamic_dtm_initial_snapshot=history[0].dynamic_dtm_initial_snapshot
        item.dynamic_dtm_explanation=history[0].dynamic_dtm_explanation
    row=suggestion(plan,history)
    assert row["distinct_dates"] == 1 and not row["can_apply"]


@pytest.mark.parametrize("change", ["farm","variety","active","future_completion","retrospective","shifted","gdd","season","reference_kind","corrected_initial"])
def test_incompatible_evidence_is_excluded(learning,change):
    _, plan, history, _=learning
    item=history[0]
    initial=json.loads(item.dynamic_dtm_initial_snapshot)
    if change == "farm": item.farm_id=2
    elif change == "variety": item.variety_id=999
    elif change == "active": item.status="active"
    elif change == "future_completion": item.completed_on=date.today()+timedelta(days=1)
    elif change == "retrospective": initial["calculated_at"]=str(item.harvests[0].harvest_date)+"T00:00:00+00:00"
    elif change == "shifted": item.sowing_date += timedelta(days=1)
    elif change == "gdd": initial["method"]="gdd"
    elif change == "season": initial["season"]="winter"
    elif change == "reference_kind": initial["reference_kind"]="transplant"
    elif change == "corrected_initial": initial["history_correction"]={"days":2}
    item.dynamic_dtm_initial_snapshot=json.dumps(initial)
    row=suggestion(plan,history)
    assert row["distinct_dates"] == 2 and not row["can_apply"]


def test_large_scatter_blocks_proposal_and_consistent_error_is_capped(learning):
    _, plan, history, _=learning
    first=history[0]
    first.harvests[0].harvest_date += timedelta(days=20)
    first.completed_on=first.harvests[0].harvest_date+timedelta(days=1)
    assert not suggestion(plan,history)["can_apply"]
    for item in history:
        item.harvests[0].harvest_date=item.sowing_date+timedelta(days=45)
        item.completed_on=item.harvests[0].harvest_date+timedelta(days=1)
    assert suggestion(plan,history)["correction_days"] == 6


def test_early_harvest_can_shorten_estimate(learning):
    _, plan, history, _=learning
    for item in history:
        item.harvests[0].harvest_date=item.sowing_date+timedelta(days=26)
    assert suggestion(plan,history)["correction_days"] == -4


def test_apply_reset_preserve_initial_catalog_dates_and_backup(learning):
    db, plan, _, client=learning
    initial=plan.dynamic_dtm_initial_snapshot
    explanation=plan.dynamic_dtm_explanation
    planned=plan.expected_harvest_date
    end=plan.predicted_harvest_end
    token=client.get('/api/planning/dtm-learning').json()['token']
    result=client.post(f'/api/planning/dtm-learning/{plan.id}/apply',json={'token':token})
    assert result.status_code == 200
    assert plan.dynamic_dtm_days == 34 and plan.predicted_harvest_end == end+timedelta(days=4)
    assert plan.variety.days_to_harvest == 30 and plan.expected_harvest_date == planned
    assert plan.dynamic_dtm_initial_snapshot == initial and plan.dynamic_dtm_confidence == 'low'
    assert client.post(f'/api/planning/dtm-learning/{plan.id}/apply',json={'token':token}).status_code == 409
    content,_=create_backup_bytes(db); restore_parsed_backup(db,parse_backup(content)); db.expire_all()
    restored=db.scalar(select(CropPlan))
    assert json.loads(restored.dynamic_dtm_explanation)['history_correction']['days'] == 4
    report=client.get('/api/planning/dtm-learning').json()
    assert report['rows'][0]['can_reset'] and not report['rows'][0]['can_apply']
    assert client.post(f'/api/planning/dtm-learning/{restored.id}/reset',json={'token':report['token']}).status_code == 200
    assert restored.dynamic_dtm_explanation == explanation and restored.dynamic_dtm_initial_snapshot == initial


def test_changed_harvest_invalidates_proposal(learning):
    db, plan, history, client=learning
    token=client.get('/api/planning/dtm-learning').json()['token']
    history[0].harvests[0].harvest_date += timedelta(days=1); db.commit()
    assert client.post(f'/api/planning/dtm-learning/{plan.id}/apply',json={'token':token}).status_code == 409
    assert plan.dynamic_dtm_days == 30


def test_past_plan_and_gdd_target_cannot_apply(learning):
    _, plan, history, _=learning
    plan.sowing_date=date.today()
    assert not suggestion(plan,history)['can_apply']
    plan.sowing_date=date(date.today().year+1,5,15)
    current=json.loads(plan.dynamic_dtm_explanation); current['method']='gdd'
    plan.dynamic_dtm_explanation=json.dumps(current)
    assert not suggestion(plan,history)['can_apply']


def test_correction_is_cleared_by_succession_recalculation(learning):
    _, plan, _, client=learning
    token=client.get('/api/planning/dtm-learning').json()['token']
    client.post(f'/api/planning/dtm-learning/{plan.id}/apply',json={'token':token})
    initial=plan.dynamic_dtm_initial_snapshot
    plan.sowing_date += timedelta(days=2)
    store_prediction(plan,plan.variety)
    assert 'history_correction' not in json.loads(plan.dynamic_dtm_explanation)
    assert plan.dynamic_dtm_initial_snapshot == initial
