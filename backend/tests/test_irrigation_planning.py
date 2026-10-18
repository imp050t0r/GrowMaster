import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.irrigation_planning import assess, crop_cycle, load_context
from app.models import IrrigationBedProfile, IrrigationCropProfile, CropPlan
from test_irrigation import BP, CP
from test_production_planner import START, END, prepare, request, other_crop
from test_succession import setup


def configure(db, beds, crop_ids, **changes):
    for bed in beds[:2]:
        db.add(IrrigationBedProfile(farm_id=1, bed_id=bed.id, parameters=json.dumps({
            **BP, 'valve_mode': 'shared', 'opensprinkler_station_entity': 'switch.shared', **changes})))
    for cid in crop_ids:
        db.add(IrrigationCropProfile(farm_id=1, crop_id=cid, parameters=json.dumps(CP)))
    db.commit()


def test_shared_proposals_keep_bed_identity_and_compatible_crops(setup):
    db,beds,variety,_,_,client=prepare(setup)
    crop,_=other_crop(db)
    configure(db,beds,[variety.crop_id,crop.id])
    result=request(client,[variety.crop_id,crop.id]).json()
    shared=[p for p in result['proposals'] if p['bed_id'] in [b.id for b in beds[:2]]]
    assert len(shared)==2 and len({p['crop_id'] for p in shared})==2
    assert all(p['irrigation']['compatible'] for p in shared)
    assert shared[0]['irrigation']['estimated_zone_flow_l_min']==4
    assert not list(db.scalars(select(CropPlan)))


def test_conflicting_crop_is_shifted_after_other_bed_releases(setup):
    db,beds,variety,_,plan,client=prepare(setup)
    crop,_=other_crop(db)
    configure(db,beds,[variety.crop_id,crop.id])
    profile=db.scalar(select(IrrigationCropProfile).where(IrrigationCropProfile.crop_id==crop.id))
    profile.parameters=json.dumps({**CP,'kc_initial':1.5,'kc_mid':1.5,'kc_late':1.5})
    occupied=plan(bed=1)
    occupied.sowing_date=START
    occupied.expected_harvest_date=START+timedelta(days=30)
    occupied.expected_bed_release_date=START+timedelta(days=35)
    db.commit()
    result=request(client,[crop.id]).json()
    row=next(p for p in result['proposals'] if p['bed_id']==beds[0].id)
    assert row['sowing_date']==str(START+timedelta(days=36))
    assert occupied.sowing_date==START


def test_same_crop_different_phase_is_not_automatically_compatible(setup):
    db,beds,variety,_,plan,_=prepare(setup)
    configure(db,beds,[variety.crop_id])
    first=plan(); first.sowing_date=START; first.expected_harvest_date=START+timedelta(days=30)
    second=plan(bed=1); second.sowing_date=START+timedelta(days=10); second.expected_harvest_date=START+timedelta(days=40)
    db.commit()
    result=assess(crop_cycle(first),[crop_cycle(second)],load_context(db,1))
    assert not result['compatible'] and 'Kc' in result['reasons'][0]


@pytest.mark.parametrize('change',['missing_crop','missing_flow','pump','mixed_mapping','unequal_beds'])
def test_incomplete_or_invalid_shared_configuration_blocks_proposals(setup,change):
    db,beds,variety,_,_,client=prepare(setup)
    configure(db,beds,[] if change=='missing_crop' else [variety.crop_id],
              flow_l_min=None if change=='missing_flow' else 40 if change=='pump' else 2)
    if change=='mixed_mapping':
        profile=db.scalar(select(IrrigationBedProfile).where(IrrigationBedProfile.bed_id==beds[1].id))
        data=json.loads(profile.parameters);data['valve_mode']='individual';profile.parameters=json.dumps(data)
    if change=='unequal_beds': beds[1].length_m=20
    db.commit()
    result=request(client,[variety.crop_id]).json()
    assert {p['bed_id'] for p in result['proposals']}=={beds[2].id}
    assert all(p['irrigation_reasons'] for p in result['skipped_beds'])


def test_shared_valve_does_not_merge_rotation_histories(setup):
    db,beds,variety,planting,_,client=prepare(setup)
    configure(db,beds,[variety.crop_id])
    old=planting();old.status='completed';beds[0].status='empty';db.commit()
    result=request(client,[variety.crop_id]).json()
    ids={p['bed_id'] for p in result['proposals']}
    assert beds[0].id not in ids and beds[1].id in ids


def test_unknown_active_release_in_other_bed_blocks_shared_proposal(setup):
    db,beds,variety,planting,_,client=prepare(setup)
    crop,_=other_crop(db)
    configure(db,beds,[variety.crop_id,crop.id])
    active=planting();active.bed_id=beds[1].id;beds[0].status='empty';beds[1].status='growing'
    variety.harvest_methods='cut_and_regrow'
    db.commit()
    result=request(client,[crop.id]).json()
    assert beds[0].id not in {p['bed_id'] for p in result['proposals']}


def test_foreign_farm_mapping_does_not_join_shared_valve(setup):
    db,beds,variety,_,_,client=prepare(setup)
    configure(db,beds,[variety.crop_id])
    db.add(IrrigationBedProfile(farm_id=2,bed_id=beds[2].id,parameters=json.dumps({
        **BP,'flow_l_min':100,'valve_mode':'shared','opensprinkler_station_entity':'switch.shared'})))
    db.commit()
    assert len(request(client,[variety.crop_id]).json()['proposals'])==3


def test_manual_plan_cannot_bypass_shared_valve_check(setup):
    from fastapi import HTTPException
    from app.main import create_crop_plan
    from app.schemas import CropPlanCreate
    db,beds,variety,_,plan,_=prepare(setup)
    crop,other=other_crop(db)
    configure(db,beds,[variety.crop_id,crop.id])
    profile=db.scalar(select(IrrigationCropProfile).where(IrrigationCropProfile.crop_id==crop.id))
    profile.parameters=json.dumps({**CP,'kc_initial':1.5,'kc_mid':1.5,'kc_late':1.5})
    occupied=plan(bed=1);occupied.sowing_date=START;occupied.expected_harvest_date=START+timedelta(days=30)
    db.commit()
    payload=CropPlanCreate(bed_id=beds[0].id,crop_id=crop.id,variety_id=other.id,
                          sowing_date=START,expected_yield_kg=10)
    with pytest.raises(HTTPException) as error:
        create_crop_plan(payload,db)
    assert error.value.status_code==422
    assert len(list(db.scalars(select(CropPlan))))==1


def test_limit_counts_valves_not_beds(setup):
    from fastapi import HTTPException
    from app.irrigation_routes import save_bed, BedProfile
    from app.models import Bed
    db,beds,variety,_,_,_=prepare(setup)
    for index in range(72):
        bed=Bed(farm_id=1,name=f'zone {index}',width_m=1,length_m=10,status='empty')
        db.add(bed);db.flush()
        db.add(IrrigationBedProfile(farm_id=1,bed_id=bed.id,parameters=json.dumps({
            **BP,'opensprinkler_station_entity':f'switch.zone_{index}'})))
    db.commit()
    with pytest.raises(HTTPException) as error:
        save_bed(beds[0].id,BedProfile(**BP,opensprinkler_station_entity='switch.extra'),db)
    assert error.value.status_code==422
    result=save_bed(beds[0].id,BedProfile(**BP,opensprinkler_station_entity='switch.zone_0',valve_mode='shared'),db)
    assert result['opensprinkler_station_entity']=='switch.zone_0'
