import json
from datetime import timedelta
import pytest
from app.dynamic_dtm import store_prediction
from app.harvest_forecast import harvest_forecast
from app.models import Harvest
from test_succession import setup, day

def get(client,start=0,end=100):
    response=client.get(f'/api/planning/harvest-forecast?start={day(start)}&end={day(end)}')
    assert response.status_code==200
    return response.json()

def record_harvest(db,planting,offset=10,quantity=2,quality='good',farm_id=1):
    harvest=Harvest(farm_id=farm_id,bed_id=planting.bed_id,planting_id=planting.id,
                    harvest_date=day(offset),quantity_kg=quantity,quality=quality)
    db.add(harvest);db.flush();return harvest

def test_dynamic_window_includes_plan_with_fixed_date_outside_range_and_never_writes(setup):
    db,_,variety,_,plan,client=setup
    current=plan();current.expected_harvest_date=day(200)
    store_prediction(current,variety);db.commit()
    original=current.dynamic_dtm_explanation
    report=get(client)
    row=report['rows'][0]
    assert row['basis']=='dynamic' and row['center_date']==str(day(42))
    assert row['planned_harvest_date']==str(day(200)) and row['confidence']=='low'
    assert row['scheduled_first_harvest_kg']==10
    assert current.dynamic_dtm_explanation==original and current.expected_harvest_date==day(200)
    assert not db.dirty and not db.new

def test_window_overlap_never_duplicates_weekly_kilograms(setup):
    db,_,variety,_,plan,client=setup
    current=plan();store_prediction(current,variety);db.commit()
    report=get(client)
    assert sum(w['scheduled_count'] for w in report['weeks'])==1
    assert sum(w['scheduled_kg'] or 0 for w in report['weeks'])==10
    assert sum(w['window_overlap_count'] for w in report['weeks'])>1
    clipped=get(client,start=34,end=35)
    assert clipped['first_harvest_count']==1
    assert sum(w['scheduled_count'] for w in clipped['weeks'])==0
    assert all(w['scheduled_kg'] is None for w in clipped['weeks'])

@pytest.mark.parametrize('corruption',['missing','json','dates','reference'])
def test_invalid_or_stale_prediction_falls_back_without_regeneration(setup,corruption):
    db,_,variety,_,plan,client=setup
    current=plan();store_prediction(current,variety)
    if corruption=='missing':current.dynamic_dtm_explanation=None
    elif corruption=='json':current.dynamic_dtm_explanation='[1]'
    elif corruption=='dates':current.predicted_harvest_start=current.predicted_harvest_end+timedelta(days=1)
    else:current.sowing_date+=timedelta(days=1)
    db.commit();original=current.dynamic_dtm_explanation
    row=get(client)['rows'][0]
    assert row['basis']=='planned_fallback' and row['window_start']==str(current.expected_harvest_date)
    assert row['window_start']==row['window_end'] and row['warning']
    assert current.dynamic_dtm_explanation==original

def test_activated_plan_is_counted_once_with_original_quantity_and_transplant_reference(setup):
    db,_,variety,planting,plan,client=setup
    current=plan(nursery=7);current.status='activated'
    active=planting();active.sowing_date=current.sowing_date
    current.planting_id=active.id
    store_prediction(active,variety,reference_date=current.transplant_date,reference_kind='transplant')
    db.commit()
    report=get(client)
    assert report['first_harvest_count']==1
    row=report['rows'][0]
    assert row['source']=='planting' and row['source_plan_id']==current.id
    assert row['basis']=='dynamic' and row['scheduled_first_harvest_kg']==10

def test_forecast_scopes_farm_status_and_does_not_assign_unknown_quantity(setup):
    db,_,_,planting,plan,client=setup
    current=plan();cancelled=plan();cancelled.status='cancelled'
    foreign=plan();foreign.farm_id=2
    active=planting();completed=planting();completed.status='completed'
    other=planting();other.farm_id=2
    db.commit();report=get(client)
    assert {(r['source'],r['id']) for r in report['rows']}=={('plan',current.id),('planting',active.id)}
    row=next(r for r in report['rows'] if r['source']=='planting')
    assert row['planned_cycle_kg'] is None and row['quantity_reason']
    assert sum(w['unknown_quantity_count'] for w in report['weeks'])==1

def test_repeated_harvest_retains_cycle_total_without_weekly_distribution(setup):
    db,_,variety,_,plan,client=setup
    variety.harvest_methods='full_size,cut_and_regrow'
    plan();db.commit();report=get(client)
    row=report['rows'][0]
    assert row['planned_cycle_kg']==10 and row['scheduled_first_harvest_kg'] is None
    assert row['quantity_reason'] and all(w['scheduled_kg'] is None for w in report['weeks'])

def test_actual_includes_completed_harvests_excludes_future_waste_and_other_farm(setup):
    db,_,_,planting,_,client=setup
    harvested=planting();completed=planting();completed.status='completed'
    foreign=planting();foreign.farm_id=2
    record_harvest(db,harvested,offset=-2,quantity=3)
    record_harvest(db,completed,offset=-1,quantity=4)
    record_harvest(db,harvested,offset=-1,quantity=5,quality='waste')
    record_harvest(db,harvested,offset=1,quantity=9)
    record_harvest(db,foreign,offset=-1,quantity=20)
    record_harvest(db,completed,offset=-1,quantity=20,farm_id=2)
    db.commit();report=get(client,start=-7)
    assert report['actual_kg']==7 and sum(w['actual_kg'] for w in report['weeks'])==7
    assert not report['rows']

def test_future_harvest_does_not_suppress_first_harvest_or_count_as_actual(setup):
    db,_,_,planting,_,client=setup
    current=planting();record_harvest(db,current,offset=1);db.commit()
    report=get(client)
    assert report['first_harvest_count']==1 and report['actual_kg']==0

def test_overdue_window_is_flagged_and_never_shifted(setup):
    db,_,_,planting,_,client=setup
    current=planting();current.expected_harvest_date=day(-1);db.commit()
    report=get(client,start=-7,end=7)
    assert report['overdue_count']==1 and report['rows'][0]['center_date']==str(day(-1))
    assert current.expected_harvest_date==day(-1)

def test_ambiguous_linked_plan_cannot_inflate_active_quantity(setup):
    db,_,_,planting,plan,client=setup
    current=planting()
    for _ in range(2):
        linked=plan();linked.status='activated';linked.planting_id=current.id;linked.sowing_date=current.sowing_date
    db.commit();report=get(client)
    assert report['first_harvest_count']==1 and report['rows'][0]['planned_cycle_kg'] is None

@pytest.mark.parametrize('quantity',[float('nan'),float('inf'),-1,0])
def test_invalid_yield_is_unknown_instead_of_nan_or_negative(setup,quantity):
    _,_,_,_,plan,_=setup
    current=plan();current.expected_yield_kg=quantity
    report=harvest_forecast([current],[],[],day(0),day(100))
    assert report['rows'][0]['planned_cycle_kg'] is None

def test_invalid_range_and_single_day(setup):
    client=setup[-1]
    assert client.get(f'/api/planning/harvest-forecast?start={day(1)}&end={day(0)}').status_code==422
    assert client.get(f'/api/planning/harvest-forecast?start={day(0)}&end={day(367)}').status_code==422
    assert get(client,start=0,end=0)['weeks'][0]['start']==str(day(0))
