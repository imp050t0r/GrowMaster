import math
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import get_db
from app.seed_forecast_routes import router, _nursery_packages
from app.seed_inventory_service import create_lot
from test_succession import setup, day

@pytest.fixture
def nursery(setup,tmp_path,monkeypatch):
    db,_,_,_,plan,_=setup
    current=plan(start=12,nursery=7);db.commit()
    path=tmp_path/'nursery-inventory.json'
    monkeypatch.setenv('GROWMASTER_SEED_INVENTORY_FILE',str(path))
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db
    return db,current,TestClient(app),path

def lot(current,**kwargs):
    return create_lot({'crop':current.crop.name,'variety':current.variety.name,'unit':'seeds',
                       'quantity':300,'package_size':500,'expiry_date':'2099-01-01',**kwargs})

def get(client,current,**params):
    return client.get(f'/api/seed-inventory/nursery-forecast/{current.id}',params={
        'target_plants':1000,'germination_pct':95,'nursery_survival_pct':90,'reserve_pct':5,**params})

def test_requirement_pellet_packages_and_no_database_or_inventory_writes(nursery):
    db,current,client,path=nursery
    lot(current,unit='pellets');before=path.read_bytes();mtime=path.stat().st_mtime_ns
    response=get(client,current);assert response.status_code==200
    result=response.json()
    assert result['required_quantity']==1229 and result['available_quantity']==300 and result['shortage']==929
    assert result['packages'][0]['packages_to_order']==2
    assert result['packages'][0]['unit']=='pellets' and result['packages'][0]['order_quantity']==1000
    assert result['target_plants']==1000 and result['sowing_date']==str(current.sowing_date)
    assert path.read_bytes()==before and path.stat().st_mtime_ns==mtime
    assert not db.dirty and not db.new

def test_mixed_lots_expiry_and_tkw_without_false_gram_pellet_conversion(nursery):
    _,current,client,_=nursery
    lot(current,quantity=200)
    lot(current,unit='pellets',quantity=100)
    lot(current,unit='g',quantity=2,package_size=1,thousand_seed_weight_g=2)
    lot(current,quantity=400,expiry_date=str(current.sowing_date))
    lot(current,quantity=900,expiry_date=str(day(4)))
    lot(current,unit='g',quantity=50)
    lot(current,variety='Different variety',quantity=9000)
    result=get(client,current).json()
    assert result['available_quantity']==1700 and result['shortage']==0 and result['expired_quantity']==900
    assert result['stock_warnings']
    assert all(p['packages_to_order']==0 for p in result['packages'])

def test_package_suggestions_keep_grams_and_use_thousand_seed_weight(nursery):
    _,current,client,_=nursery
    lot(current,unit='g',quantity=0,package_size=1,thousand_seed_weight_g=2)
    result=get(client,current).json();package=result['packages'][0]
    assert package['seeds_per_package']==500 and package['packages_to_order']==3
    assert package['unit']=='g' and package['order_quantity']==3

def test_fractional_seed_stock_is_not_used_as_whole_seeds(nursery):
    _,current,client,_=nursery
    lot(current,quantity=300.9)
    result=get(client,current).json()
    assert result['available_quantity']==300 and result['shortage']==929

def test_unknown_package_and_missing_tkw_are_explicit(nursery):
    _,current,client,_=nursery
    lot(current,unit='g',quantity=2,package_size=1)
    result=get(client,current).json()
    assert result['shortage']==1229 and result['packages']==[] and result['stock_warnings']

def test_manual_percentages_are_used_without_lot_defaults(nursery):
    _,current,client,_=nursery
    lot(current,germination_pct=100)
    result=get(client,current,target_plants=100,germination_pct=50,nursery_survival_pct=50,reserve_pct=0).json()
    assert result['required_quantity']==400 and result['shortage']==100

@pytest.mark.parametrize('status',['activated','cancelled'])
def test_changed_plan_status_is_rejected(nursery,status):
    db,current,client,_=nursery
    current.status=status;db.commit()
    assert get(client,current).status_code==409

def test_direct_sowing_foreign_farm_and_past_seed_date_are_rejected(nursery):
    db,current,client,_=nursery
    current.transplant_date=None;db.commit();assert get(client,current).status_code==422
    current.transplant_date=day(12);current.farm_id=2;db.commit();assert get(client,current).status_code==404
    current.farm_id=1;current.sowing_date=day(-1);db.commit();assert get(client,current).status_code==422

def test_invalid_transplant_date_is_rejected(nursery):
    db,current,client,_=nursery
    current.transplant_date=day(1);db.commit()
    assert get(client,current).status_code==422

@pytest.mark.parametrize('params',[{'target_plants':0},{'target_plants':1000001},{'target_plants':1.5},
    {'germination_pct':0},{'germination_pct':101},{'germination_pct':'nan'},{'germination_pct':'inf'},
    {'germination_pct':'1e-300'},{'nursery_survival_pct':0},{'nursery_survival_pct':101},
    {'nursery_survival_pct':'nan'},{'reserve_pct':-1},{'reserve_pct':101},{'reserve_pct':'nan'}])
def test_invalid_quantity_and_percentages_are_rejected(nursery,params):
    _,current,client,_=nursery
    assert get(client,current,**params).status_code==422

def test_missing_parameters_require_explicit_values(nursery):
    _,current,client,_=nursery
    assert client.get(f'/api/seed-inventory/nursery-forecast/{current.id}').status_code==422

def test_no_lots_still_reports_count_without_inventing_packages(nursery):
    _,current,client,path=nursery
    result=get(client,current).json()
    assert result['required_quantity']==1229 and result['available_quantity']==0
    assert result['packages']==[] and not path.exists()

@pytest.mark.parametrize('package',[None,-1,0,float('nan'),float('inf'),.5])
def test_invalid_count_packages_are_not_suggested(package):
    assert _nursery_packages([{'unit':'seeds','package_size':package}],10)==[]
