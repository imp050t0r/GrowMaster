import json
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func

from app.models import CropPlan, Planting, Task, IrrigationBedProfile, IrrigationCropProfile
from app.successor_routes import succession_state
from test_irrigation import CP
from test_irrigation_planning import configure
from test_production_planner import other_crop
from test_succession import setup, day


def test_shift_preview_blocks_new_phase_conflict_without_mutation(setup):
    db, beds, variety, planting, plan, client = setup
    configure(db, beds, [variety.crop_id])
    planting(); first = plan(); plan(bed=1)
    db.commit()
    report = succession_state(db)[3]
    group = next(g for g in report['beds'] if g['bed_id'] == beds[0].id)
    assert not group['can_apply'] and group['plans'][0]['irrigation_reasons']
    assert first.sowing_date == day(12) and not db.dirty
    response = client.post(f'/api/planning/successions/{beds[0].id}/apply', json={'token': report['token']})
    assert response.status_code == 409 and first.sowing_date == day(12)


def test_shift_compatible_shared_group_still_applies(setup):
    db, beds, variety, planting, plan, client = setup
    configure(db, beds, [variety.crop_id])
    profile = db.scalar(select(IrrigationCropProfile))
    profile.parameters = json.dumps({**CP, 'kc_initial': 1, 'kc_mid': 1, 'kc_late': 1})
    planting(); first = plan(); plan(bed=1)
    db.commit()
    report = succession_state(db)[3]
    group = next(g for g in report['beds'] if g['bed_id'] == beds[0].id)
    assert group['can_apply']
    response = client.post(f'/api/planning/successions/{beds[0].id}/apply', json={'token': report['token']})
    assert response.status_code == 200 and first.sowing_date == day(21)


def test_move_preview_excludes_incompatible_shared_destination(setup):
    db, beds, variety, planting, plan, client = setup
    configure(db, [beds[1], beds[2]], [variety.crop_id])
    planting(); source = plan(); peer = plan(bed=2, start=22)
    db.commit()
    report = succession_state(db)[3]
    row = next(r for g in report['beds'] for r in g['plans'] if r['plan_id'] == source.id)
    assert beds[1].id not in {b['id'] for b in row['alternative_beds']}
    result = client.post(f'/api/planning/successions/plans/{source.id}/move',
                         json={'token': report['token'], 'bed_id': beds[1].id})
    assert result.status_code == 409 and source.bed_id == beds[0].id

    assert peer.sowing_date == day(22)


@pytest.mark.parametrize('profile_kind', ['bed', 'crop'])
def test_profile_change_invalidates_open_succession_token(setup, profile_kind):
    db, beds, variety, planting, plan, client = setup
    configure(db, [beds[1], beds[2]], [variety.crop_id])
    planting(); source = plan(); db.commit()
    token = succession_state(db)[3]['token']
    model = IrrigationBedProfile if profile_kind == 'bed' else IrrigationCropProfile
    row = db.scalar(select(model))
    data = json.loads(row.parameters); data['source'] = 'New calibration'; row.parameters = json.dumps(data)
    db.commit()
    result = client.post(f'/api/planning/successions/plans/{source.id}/move',
                         json={'token': token, 'bed_id': beds[1].id})
    assert result.status_code == 409 and source.bed_id == beds[0].id
    fresh = succession_state(db)[3]['token']
    result = client.post(f'/api/planning/successions/plans/{source.id}/move',
                         json={'token': fresh, 'bed_id': beds[1].id})
    assert result.status_code == 200 and source.bed_id == beds[1].id


@pytest.mark.parametrize('activate', [False, True])
def test_activation_and_direct_sowing_recheck_current_zone_atomically(setup, activate):
    from app.main import activate_crop_plan, create_planting
    from app.schemas import CropPlanActivate, PlantingCreate
    db, beds, variety, _, plan, _ = setup
    other, other_variety = other_crop(db)
    configure(db, beds, [variety.crop_id, other.id])
    profile = db.scalar(select(IrrigationCropProfile).where(IrrigationCropProfile.crop_id == other.id))
    profile.parameters = json.dumps({**CP, 'kc_initial': 1.5, 'kc_mid': 1.5, 'kc_late': 1.5})
    source = plan(start=0)
    peer = plan(bed=1, start=0); peer.crop_id = other.id; peer.variety_id = other_variety.id
    db.commit()
    with pytest.raises(HTTPException) as error:
        if activate:
            activate_crop_plan(source.id, CropPlanActivate(override_rotation=True), db)
        else:
            create_planting(PlantingCreate(bed_id=beds[0].id, crop_id=variety.crop_id,
                                          variety_id=variety.id, sowing_date=date.today(), override_rotation=True), db)
    assert error.value.status_code == 409
    assert 'Skupni ventil' in error.value.detail
    assert source.status == 'planned' and beds[0].status == 'empty'
    assert db.scalar(select(func.count()).select_from(Planting)) == 0
    assert db.scalar(select(func.count()).select_from(Task)) == 0


@pytest.mark.parametrize('activate', [False, True])
def test_compatible_zone_allows_activation_and_creates_tasks(setup, activate):
    from app.main import activate_crop_plan, create_planting
    from app.schemas import CropPlanActivate, PlantingCreate
    db, beds, variety, _, plan, _ = setup
    configure(db, beds, [variety.crop_id])
    profile = db.scalar(select(IrrigationCropProfile))
    profile.parameters = json.dumps({**CP, 'kc_initial': 1, 'kc_mid': 1, 'kc_late': 1})
    source = plan(start=0); plan(bed=1, start=0); db.commit()
    if activate:
        activate_crop_plan(source.id, CropPlanActivate(override_rotation=True), db)
        assert source.status == 'activated'
    else:
        create_planting(PlantingCreate(bed_id=beds[0].id, crop_id=variety.crop_id,
                                      variety_id=variety.id, sowing_date=date.today(), override_rotation=True), db)
    assert beds[0].status == 'growing'
    assert db.scalar(select(func.count()).select_from(Planting)) == 1
    assert db.scalar(select(func.count()).select_from(Task)) == 3


def test_release_extension_cannot_create_shared_zone_conflict(setup):
    db, beds, variety, _, plan, client = setup
    other, other_variety = other_crop(db)
    configure(db, beds, [variety.crop_id, other.id])
    profile = db.scalar(select(IrrigationCropProfile).where(IrrigationCropProfile.crop_id == other.id))
    profile.parameters = json.dumps({**CP, 'kc_initial': 1.5, 'kc_mid': 1.5, 'kc_late': 1.5})
    source = plan(start=12)
    peer = plan(bed=1, start=43); peer.crop_id = other.id; peer.variety_id = other_variety.id
    db.commit()
    token = succession_state(db)[3]['token']
    response = client.put(f'/api/planning/successions/plans/{source.id}/release',
                          json={'token': token, 'expected_bed_release_date': day(50).isoformat()})
    assert response.status_code == 409 and 'Skupni ventil' in response.json()['detail']
    assert source.expected_bed_release_date is None
