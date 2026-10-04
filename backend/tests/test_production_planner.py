from datetime import date,timedelta
import pytest
from app.models import Crop,Variety
from test_succession import setup

START=date(date.today().year+1,5,1)
END=START+timedelta(days=120)

def prepare(setup):
    db,beds,variety,planting,plan,client=setup
    variety.planting_method='direct'
    db.commit()
    return db,beds,variety,planting,plan,client

def request(client,selected_ids,**kwargs):
    return client.post('/api/planning/production-proposals',json={'start':str(START),'end':str(END),'crop_ids':selected_ids,'max_beds':5,**kwargs})

def other_crop(db,name='Other crop',family='Otheraceae',method='direct'):
    crop=Crop(name=name,family=family,category='Domača');db.add(crop);db.flush()
    variety=Variety(crop_id=crop.id,name='Other cultivar',days_to_harvest=30,days_spring=30,
                    days_summer=30,days_autumn=30,days_winter=30,harvest_methods='full_size',planting_method=method)
    db.add(variety);db.flush();return crop,variety

def test_proposal_is_future_explained_and_never_writes_or_invents_yield(setup):
    db,beds,variety,_,_,client=prepare(setup)
    response=request(client,[variety.crop_id]);assert response.status_code==200
    report=response.json();assert len(report['proposals'])==3 and report['method']=='local_rules'
    for row in report['proposals']:
        assert row['sowing_date']==str(START) and row['expected_yield_kg'] is None
        assert row['predicted_harvest_start']<=row['expected_harvest_date']<=row['predicted_harvest_end']<=str(END)
        assert row['confidence']=='low' and row['reasons'] and row['warnings']
    assert not db.dirty and not db.new
    assert all(b.status=='empty' for b in beds)

def test_balances_selected_crops_and_honors_max_beds(setup):
    db,_,variety,_,_,client=prepare(setup)
    crop,_=other_crop(db);db.commit()
    report=request(client,[variety.crop_id,crop.id],max_beds=2).json()
    assert len(report['proposals'])==2
    assert {p['crop_id'] for p in report['proposals']}=={variety.crop_id,crop.id}
    assert not report['unassigned_crops']

def test_farm_status_and_active_plantings_are_excluded(setup):
    db,beds,variety,planting,_,client=prepare(setup)
    current=planting();beds[0].status='empty'
    beds[1].farm_id=2
    beds[2].status='resting';db.commit()
    report=request(client,[variety.crop_id]).json()
    assert not report['proposals']
    assert {r['bed_id'] for r in report['skipped_beds']}=={beds[0].id,beds[2].id}
    assert not db.dirty

def test_unknown_existing_release_does_not_allow_overlap(setup):
    db,beds,variety,_,plan,client=prepare(setup)
    crop,repeated=other_crop(db)
    repeated.harvest_methods='cut_and_regrow'
    occupied=plan();occupied.crop_id=crop.id;occupied.variety_id=repeated.id
    occupied.sowing_date=START-timedelta(days=10);occupied.expected_harvest_date=START+timedelta(days=10)
    db.commit();report=request(client,[variety.crop_id]).json()
    assert beds[0].id not in {p['bed_id'] for p in report['proposals']}

def test_shifts_after_confirmed_release_and_preserves_existing_plan(setup):
    db,beds,variety,_,plan,client=prepare(setup)
    crop,_=other_crop(db);occupied=plan()
    occupied.sowing_date=START;occupied.expected_harvest_date=START+timedelta(days=30)
    occupied.expected_bed_release_date=START+timedelta(days=35);db.commit()
    report=request(client,[crop.id]).json()
    row=next(p for p in report['proposals'] if p['bed_id']==beds[0].id)
    assert row['sowing_date']==str(START+timedelta(days=36))
    assert occupied.sowing_date==START and occupied.expected_bed_release_date==START+timedelta(days=35)

def test_next_planned_family_is_not_invalidated_by_inserting_same_family(setup):
    db,beds,variety,_,plan,client=prepare(setup)
    upcoming=plan();upcoming.sowing_date=START+timedelta(days=80);upcoming.expected_harvest_date=END+timedelta(days=10)
    db.commit();report=request(client,[variety.crop_id]).json()
    assert beds[0].id not in {p['bed_id'] for p in report['proposals']}

def test_completed_history_rotation_and_foreign_history_scoping(setup):
    db,beds,variety,planting,_,client=prepare(setup)
    previous=planting();previous.status='completed';beds[0].status='empty'
    foreign=planting();foreign.bed_id=beds[1].id;foreign.farm_id=2;foreign.status='completed'
    db.commit();report=request(client,[variety.crop_id]).json()
    ids={p['bed_id'] for p in report['proposals']}
    assert beds[0].id not in ids and beds[1].id in ids

def test_last_crop_family_is_used_without_history(setup):
    db,beds,variety,_,_,client=prepare(setup)
    beds[0].last_crop_family=variety.crop.family;db.commit()
    assert beds[0].id not in {p['bed_id'] for p in request(client,[variety.crop_id]).json()['proposals']}

def test_transplants_require_known_nursery_and_keep_reference_date(setup):
    db,_,variety,_,_,client=prepare(setup)
    variety.planting_method='transplant';variety.nursery_days=None;db.commit()
    assert not request(client,[variety.crop_id]).json()['proposals']
    variety.nursery_days=21;db.commit()
    row=request(client,[variety.crop_id]).json()['proposals'][0]
    assert row['sowing_date']==str(START) and row['transplant_date']==str(START+timedelta(days=21))
    assert row['expected_harvest_date']==str(START+timedelta(days=51))

@pytest.mark.parametrize('change',['repeated','missing_method','too_short','wrong_season'])
def test_unsupported_or_unfitting_candidates_are_explicitly_unassigned(setup,change):
    db,_,variety,_,_,client=prepare(setup)
    overrides={}
    if change=='repeated':variety.harvest_methods='full_size,cut_and_regrow'
    elif change=='missing_method':variety.planting_method=None
    elif change=='too_short':overrides['end']=str(START+timedelta(days=10))
    else:
        variety.crop.name='Paradižnik'
        overrides.update(start=str(date(START.year,11,1)),end=str(date(START.year+1,2,1)))
    db.commit();report=request(client,[variety.crop_id],**overrides).json()
    assert not report['proposals'] and report['unassigned_crops'] and report['skipped_beds']

@pytest.mark.parametrize('overrides',[{'crop_ids':[]},{'crop_ids':[999999]},{'crop_ids':[-1]},
    {'crop_ids':[1]*11},{'max_beds':0},{'max_beds':101},{'start':str(date.today())},
    {'end':str(START-timedelta(days=1))},{'end':str(START+timedelta(days=367))},{'unexpected':1}])
def test_invalid_inputs_are_rejected(setup,overrides):
    *_,variety,planting,plan,client=prepare(setup)
    assert request(client,[variety.crop_id],**overrides).status_code==422

def test_cancelled_plan_does_not_block_bed(setup):
    db,beds,variety,_,plan,client=prepare(setup)
    cancelled=plan();cancelled.status='cancelled';cancelled.sowing_date=START;cancelled.expected_harvest_date=END
    db.commit();report=request(client,[variety.crop_id]).json()
    assert beds[0].id in {p['bed_id'] for p in report['proposals']}

