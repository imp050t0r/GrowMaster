from datetime import date
from copy import deepcopy
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import get_db
from app.seed_forecast_routes import _allocate_lots, _package_size_for_lots, router
from test_succession import setup, day

def test_allocation_expiry_and_no_mutation():
    lots=[{'id':1,'quantity':8,'unit':'g','expiry_date':'2027-04-01'}, {'id':2,'quantity':3,'unit':'g','expiry_date':'2027-05-01'}]
    original=deepcopy(lots)
    plans=[{'sowing_date':date(2027,4,1),'required_quantity':5}, {'sowing_date':date(2027,4,2),'required_quantity':5}]
    result=_allocate_lots(lots,plans,'g')
    assert [p['shortage'] for p in plans]==[0,2]
    assert result['shortage']==2 and result['available']==8
    assert result['expired_quantity']==3
    assert lots==original

@pytest.mark.parametrize('lot', [
    {'quantity':100,'unit':'seeds'},
    {'quantity':100,'unit':'pellets','thousand_seed_weight_g':2},
    {'quantity':5,'unit':'g','expiry_date':'bad'},
    {'quantity':float('nan'),'unit':'g'},
    {'quantity':-1,'unit':'g'},
])
def test_invalid_lots_never_cover_plan(lot):
    p=[{'sowing_date':date(2027,4,1),'required_quantity':2}]
    result=_allocate_lots([lot],p,'g')
    assert result['shortage']==2 and result['warnings']

def test_count_conversion_and_unknown_expiry_warning():
    p=[{'sowing_date':date(2027,4,1),'required_quantity':2}]
    result=_allocate_lots([{'quantity':1000,'unit':'seeds','thousand_seed_weight_g':2}],p,'g')
    assert result['shortage']==0 and result['warnings']
    assert _package_size_for_lots([{'unit':'pellets','package_size':1000,'thousand_seed_weight_g':2}], 'g') is None

def test_route_correct_quantity_packs_and_read_only(setup,monkeypatch):
    import app.seed_forecast_routes as module
    db, beds, _, _, plan, _=setup
    current=plan(start=12,nursery=0); current.transplant_date=None
    current.variety.seed_rate_g_m2=2
    cancelled=plan(start=12); cancelled.status='cancelled'
    other=plan(start=12); other.farm_id=2
    db.commit()
    lot={'id':1,'quantity':0,'unit':'g','package_size':10,'expiry_date':'2099-01-01'}
    calls=[]
    monkeypatch.setattr(module,'list_lots',lambda crop,variety: calls.append((crop,variety)) or [lot])
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db
    response=TestClient(app).get(f'/api/seed-inventory/forecast?start_date={day(0)}&horizon_days=60')
    assert response.status_code==200
    data=response.json();assert data['planned_sowings']==1
    item=data['items'][0]
    expected=round(2*beds[0].width_m*beds[0].length_m*1.05,2)
    assert item['required_quantity']==expected
    assert item['packages_to_order']==__import__('math').ceil(expected/10)
    assert item['first_shortage_date']==str(day(12))
    assert calls==[(current.crop.name,current.variety.name)]
    assert lot['quantity']==0 and not db.dirty and not db.new

def test_transplants_report_missing_requirements(setup,monkeypatch):
    import app.seed_forecast_routes as module
    db,_,_,_,plan,_=setup
    plan(start=12,nursery=7);db.commit()
    monkeypatch.setattr(module,'list_lots',lambda *_:pytest.fail('Should not allocate unknown requirements'))
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db
    data=TestClient(app).get(f'/api/seed-inventory/forecast?start_date={day(0)}&horizon_days=60').json()
    assert not data['items'] and data['summary']['missing_seed_rate']==1
