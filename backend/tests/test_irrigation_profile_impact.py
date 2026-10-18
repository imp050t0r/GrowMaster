import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.dynamic_dtm import store_prediction
from app.dtm_learning import apply_suggestion, suggestion
from app.irrigation_routes import router
from app.models import Bed, Crop, CropPlan, IrrigationBedProfile, IrrigationCropProfile, Planting, Variety
from test_dtm_learning import learning
from test_irrigation import BP, CP
from test_irrigation_planning import configure


def shared(learning, constant=False):
    db, plan, history, client = learning
    bed = Bed(farm_id=1, name='18', width_m=.8, length_m=15, status='empty')
    db.add(bed); db.flush()
    peer = CropPlan(farm_id=1, bed_id=bed.id, crop_id=plan.crop_id, variety_id=plan.variety_id,
                    sowing_date=plan.sowing_date, expected_harvest_date=plan.expected_harvest_date,
                    expected_yield_kg=10, status='planned', series_id='peer')
    store_prediction(peer, plan.variety); db.add(peer)
    configure(db, [db.get(Bed, plan.bed_id), bed], [plan.crop_id])
    if constant:
        profile = db.scalar(select(IrrigationCropProfile))
        profile.parameters = json.dumps({**CP, 'kc_initial': 1, 'kc_mid': 1, 'kc_late': 1})
        db.commit()
    client.app.include_router(router)
    return db, plan, peer, history, client


def test_dtm_conflict_preview_and_confirmation_preserve_plan(learning):
    db, plan, peer, history, client = shared(learning)
    for item in history:
        item.harvests[0].harvest_date = item.sowing_date + timedelta(days=26)
    db.commit()
    before = plan.dynamic_dtm_explanation
    report = client.get('/api/planning/dtm-learning').json()
    row = next(r for r in report['rows'] if r['plan_id'] == plan.id)
    assert not row['can_apply'] and row['irrigation_reasons']['apply']
    assert not db.dirty
    assert client.post(f'/api/planning/dtm-learning/{plan.id}/apply', json={'token': report['token']}).status_code == 409
    db.refresh(plan)
    assert plan.dynamic_dtm_explanation == before and peer.dynamic_dtm_days == 30


def test_compatible_dtm_correction_is_saved(learning):
    _, plan, _, _, client = shared(learning, constant=True)
    report = client.get('/api/planning/dtm-learning').json()
    assert client.post(f'/api/planning/dtm-learning/{plan.id}/apply', json={'token': report['token']}).status_code == 200
    assert plan.dynamic_dtm_days == 34


def test_reset_cannot_break_shared_phase_alignment(learning):
    db, plan, peer, history, client = shared(learning)
    for item in history:
        item.harvests[0].harvest_date = item.sowing_date + timedelta(days=26)
    apply_suggestion(plan, suggestion(plan, history))
    apply_suggestion(peer, suggestion(peer, history))
    db.commit()
    before = plan.dynamic_dtm_explanation
    report = client.get('/api/planning/dtm-learning').json()
    row = next(r for r in report['rows'] if r['plan_id'] == plan.id)
    assert not row['can_reset'] and row['irrigation_reasons']['reset']
    assert client.post(f'/api/planning/dtm-learning/{plan.id}/reset', json={'token': report['token']}).status_code == 409
    db.refresh(plan)
    assert plan.dynamic_dtm_explanation == before


def test_profile_change_invalidates_open_dtm_proposal(learning):
    db, plan, _, _, client = shared(learning, constant=True)
    report = client.get('/api/planning/dtm-learning').json()
    profile = db.scalar(select(IrrigationCropProfile))
    data = json.loads(profile.parameters); data['source'] = 'Updated measurement'
    profile.parameters = json.dumps(data); db.commit()
    assert client.post(f'/api/planning/dtm-learning/{plan.id}/apply', json={'token': report['token']}).status_code == 409
    assert plan.dynamic_dtm_days == 30


def test_measured_flow_is_saved_with_persistent_conflicts_and_can_be_reconciled(learning):
    db, plan, peer, _, client = shared(learning)
    before = plan.dynamic_dtm_explanation
    assert client.get('/api/irrigation/profiles').json()['planning_conflicts'] == []
    payload = {**BP, 'valve_mode': 'shared', 'opensprinkler_station_entity': 'switch.shared', 'flow_l_min': 3}
    result = client.put(f'/api/irrigation/beds/{plan.bed_id}', json=payload)
    assert result.status_code == 200
    conflicts = result.json()['planning_conflicts']
    assert {r['record_id'] for r in conflicts} == {plan.id, peer.id}
    assert all(r['record_type'] == 'plans' and r['reasons'] for r in conflicts)
    assert client.get('/api/irrigation/profiles').json()['planning_conflicts'] == conflicts
    stored = db.scalar(select(IrrigationBedProfile).where(IrrigationBedProfile.bed_id == plan.bed_id))
    assert json.loads(stored.parameters)['flow_l_min'] == 3
    assert 'planning_conflicts' not in json.loads(stored.parameters)
    assert plan.dynamic_dtm_explanation == before
    result = client.put(f'/api/irrigation/beds/{peer.bed_id}', json=payload)
    assert result.status_code == 200 and result.json()['planning_conflicts'] == []


@pytest.mark.parametrize('status', ['completed', 'cancelled'])
def test_inactive_plans_are_excluded_from_profile_warnings(learning, status):
    db, plan, peer, _, client = shared(learning)
    plan.status = peer.status = status; db.commit()
    payload = {**BP, 'valve_mode': 'shared', 'opensprinkler_station_entity': 'switch.shared', 'flow_l_min': 3}
    result = client.put(f'/api/irrigation/beds/{plan.bed_id}', json=payload)
    assert result.status_code == 200 and result.json()['planning_conflicts'] == []


def test_new_active_peer_invalidates_open_dtm_proposal(learning):
    db, plan, peer, _, client = shared(learning, constant=True)
    report = client.get('/api/planning/dtm-learning').json()
    active = Planting(farm_id=1, bed_id=peer.bed_id, crop_id=plan.crop_id, variety_id=plan.variety_id,
                      sowing_date=plan.sowing_date, expected_harvest_date=plan.expected_harvest_date,
                      status='active')
    store_prediction(active, plan.variety); db.add(active); db.commit()
    assert client.post(f'/api/planning/dtm-learning/{plan.id}/apply', json={'token': report['token']}).status_code == 409
    assert plan.dynamic_dtm_days == 30


def test_crop_profile_change_reports_active_and_planned_conflicts(learning):
    db, plan, peer, _, client = shared(learning)
    crop = Crop(name='Other crop', family='Otheraceae', category='Domača')
    db.add(crop); db.flush()
    variety = Variety(crop_id=crop.id, name='Other cultivar', days_to_harvest=30,
                      days_spring=30, days_summer=30, days_autumn=30, days_winter=30,
                      harvest_methods='full_size')
    db.add(variety); db.flush()
    peer.status = 'cancelled'
    active = Planting(farm_id=1, bed_id=peer.bed_id, crop_id=crop.id, variety_id=variety.id,
                      sowing_date=plan.sowing_date, expected_harvest_date=plan.expected_harvest_date,
                      status='active')
    store_prediction(active, variety); db.add(active)
    db.add(IrrigationCropProfile(farm_id=1, crop_id=crop.id, parameters=json.dumps(CP)))
    db.commit()
    result = client.put(f'/api/irrigation/crops/{crop.id}', json={**CP, 'root_depth_m': .6})
    assert result.status_code == 200
    assert {(r['record_type'], r['record_id']) for r in result.json()['planning_conflicts']} == {
        ('plans', plan.id), ('plantings', active.id)}
    assert client.get('/api/irrigation/profiles').json()['planning_conflicts'] == result.json()['planning_conflicts']
