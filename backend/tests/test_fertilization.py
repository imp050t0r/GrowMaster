import hashlib
import json
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.fertilization_routes import router
from app.models import Farm, Crop, Variety, Bed, Planting, Harvest, FertilizationApplication, FertilizationPlan
from app.migrations import add_fertilization_schema
from app.backups import create_backup_bytes, parse_backup, canonical_json, restore_parsed_backup


@pytest.fixture
def fertilizer():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        db.add_all([Farm(id=1,name="Doma"),Farm(id=2,name="Tuja"),Crop(id=1,name="Zelje",family="A",category="B")]);db.flush()
        db.add(Variety(id=1,crop_id=1,name="Test",days_to_harvest=60,days_spring=60,days_summer=60,days_autumn=60,days_winter=60));db.flush()
        db.add_all([Bed(id=1,farm_id=1,name="A",width_m=1,length_m=10),Bed(id=2,farm_id=2,name="B",width_m=1,length_m=10)]);db.flush()
        for i in [1,2]:
            db.add(Planting(id=i,farm_id=i,bed_id=i,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),expected_harvest_date=date.today()+timedelta(days=50),status="active"))
        db.commit()
        app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db
        with TestClient(app) as client:
            yield db, client, engine
    engine.dispose()


def dose(**changes):
    return {"day":str(date.today()),"area_m2":10,"material":"Testno gnojilo","quantity_kg":2,
        "n_pct":10,"p2o5_pct":5,"k2o_pct":20,"composition_source":"Deklaracija",**changes}


def overview(c):
    response=c.get('/api/fertilization/beds/1');assert response.status_code==200
    return response.json()


def plan(c, **changes):
    return c.post('/api/fertilization/beds/1/plans',json={**dose(),"planting_id":1,
        "rationale":"Ročno preverjen odmerek; upoštevana zgodovina", "context_version":overview(c)['context_version'],**changes})


def confirm(c, plan_id):
    return c.post(f'/api/fertilization/plans/{plan_id}/confirm',json={"reviewer":"Ana","context_version":overview(c)['context_version']})


def soil(c):
    return c.post('/api/fertilization/beds/1/soil-tests',json={"sampled_on":str(date.today()),"source":"Laboratorij",
        "sample_area":"Greda A","method":"AL","nutrient_unit":"mg P2O5/K2O na 100 g","ph":6.5,"phosphorus":12,"potassium":20})


def test_manual_lifecycle_never_counts_planned_or_confirmed_as_applied(fertilizer):
    db,c,_=fertilizer
    assert soil(c).status_code==201
    pid=plan(c).json()['id']
    assert overview(c)['declared_totals']['n']['known_kg']==0
    assert confirm(c,pid).status_code==200
    assert overview(c)['applications']==[]
    assert overview(c)['declared_totals']['n']['known_kg']==0
    result=c.post(f'/api/fertilization/plans/{pid}/complete',json={'applied_on':str(date.today())})
    assert result.status_code==201
    report=overview(c)
    assert report['declared_totals']=={'n':{'known_kg':.2,'unknown_applications':0},'p2o5':{'known_kg':.1,'unknown_applications':0},'k2o':{'known_kg':.4,'unknown_applications':0}}
    assert not report['automatic_execution']
    assert c.post(f'/api/fertilization/plans/{pid}/complete',json={'applied_on':str(date.today())}).status_code==409
    assert len(db.scalars(select(FertilizationApplication)).all())==1
    assert report['plans'][0]['reviewer']=='Ana'


def test_unknown_composition_and_void_preserve_history(fertilizer):
    _,c,_=fertilizer
    payload=dose(n_pct=None,p2o5_pct=None,k2o_pct=None,composition_source='')
    aid=c.post('/api/fertilization/beds/1/applications',json=payload).json()['id']
    assert overview(c)['declared_totals']['n']=={'known_kg':0,'unknown_applications':1}
    assert c.post(f'/api/fertilization/applications/{aid}/void',json={'reason':'Napačen zapis'}).status_code==200
    report=overview(c)
    assert report['declared_totals']['n']=={'known_kg':0,'unknown_applications':0}
    assert report['applications'][0]['void_reason']=='Napačen zapis'


@pytest.mark.parametrize('change',[{'area_m2':11},{'area_m2':0},{'quantity_kg':-1},{'n_pct':101},
    {'n_pct':80,'p2o5_pct':30},{'composition_source':''},{'material':' '},
    {'day':str(date.today()+timedelta(days=1))},{'quantity_kg':'NaN'},{'quantity_kg':'Infinity'}, {'unexpected':True}])
def test_invalid_actual_inputs_rejected_without_writes(fertilizer, change):
    db,c,_=fertilizer
    assert c.post('/api/fertilization/beds/1/applications',json=dose(**change)).status_code==422
    assert not db.scalar(select(FertilizationApplication))


@pytest.mark.parametrize('path', ['applications','plans','soil-tests'])
def test_other_farm_records_cannot_be_created(fertilizer,path):
    _,c,_=fertilizer
    payload=dose()
    if path=='plans':payload.update(planting_id=2,rationale='Test',context_version='a'*64)
    if path=='soil-tests':payload={'sampled_on':str(date.today()),'source':'L','sample_area':'B','method':'AL','nutrient_unit':'mg','ph':6}
    assert c.post(f'/api/fertilization/beds/2/{path}',json=payload).status_code==404
    assert c.get('/api/fertilization/beds/2').status_code==404


def test_foreign_planting_and_foreign_plan_are_hidden(fertilizer):
    db,c,_=fertilizer
    assert plan(c,planting_id=2).status_code==404
    assert c.post('/api/fertilization/beds/1/applications',json=dose(planting_id=2)).status_code==404
    db.add(FertilizationPlan(id=20,farm_id=2,bed_id=2,planting_id=2,parameters='{}',context='{}'));db.commit()
    assert confirm(c,20).status_code==404
    assert c.post('/api/fertilization/plans/20/cancel',json={}).status_code==404


@pytest.mark.parametrize('change',['analysis','application','harvest','planting','bed'])
def test_changed_context_blocks_confirmation_and_completion(fertilizer,change):
    db,c,_=fertilizer
    pid=plan(c).json()['id'];assert confirm(c,pid).status_code==200
    if change=='analysis':soil(c)
    if change=='application':c.post('/api/fertilization/beds/1/applications',json=dose())
    if change=='harvest':
        db.add(Harvest(farm_id=1,bed_id=1,planting_id=1,harvest_date=date.today(),quantity_kg=2,quality='good'));db.commit()
    if change=='planting':db.get(Planting,1).status='completed';db.commit()
    if change=='bed':db.get(Bed,1).length_m=9;db.commit()
    assert overview(c)['plans'][0]['stale']
    assert confirm(c,pid).status_code==409
    assert c.post(f'/api/fertilization/plans/{pid}/complete',json={'applied_on':str(date.today())}).status_code==409
    assert not db.scalar(select(FertilizationApplication).where(FertilizationApplication.plan_id==pid))


def test_stale_creation_and_missing_confirmation_rejected(fertilizer):
    _,c,_=fertilizer
    assert plan(c,context_version='0'*64).status_code==409
    assert plan(c,day=str(date.today()-timedelta(days=1))).status_code==422
    pid=plan(c).json()['id']
    assert c.post(f'/api/fertilization/plans/{pid}/complete',json={'applied_on':str(date.today())}).status_code==409
    assert c.post(f'/api/fertilization/plans/{pid}/cancel',json={}).status_code==200
    assert confirm(c,pid).status_code==409


def test_soil_validation_and_future_completion(fertilizer):
    _,c,_=fertilizer
    payload={'sampled_on':str(date.today()),'source':'L','sample_area':'A','method':'AL','nutrient_unit':'mg'}
    assert c.post('/api/fertilization/beds/1/soil-tests',json=payload).status_code==422
    assert c.post('/api/fertilization/beds/1/soil-tests',json={**payload,'ph':6,'sampled_on':str(date.today()+timedelta(days=1))}).status_code==422
    pid=plan(c).json()['id'];confirm(c,pid)
    assert c.post(f'/api/fertilization/plans/{pid}/complete',json={'applied_on':str(date.today()+timedelta(days=1))}).status_code==422


def test_context_preserves_previous_crop_and_applications_after_new_planting(fertilizer):
    db,c,_=fertilizer
    c.post('/api/fertilization/beds/1/applications',json=dose(planting_id=1))
    db.get(Planting,1).status='completed'
    db.add(Planting(id=3,farm_id=1,bed_id=1,crop_id=1,variety_id=1,sowing_date=date.today(),expected_harvest_date=date.today()+timedelta(days=50),status='active'));db.commit()
    report=overview(c)
    assert [p['id'] for p in report['plantings']]==[1,3]
    assert report['applications'][0]['planting_id']==1
    assert report['declared_totals']['n']['known_kg']==.2
    assert plan(c,planting_id=3).status_code==201


def test_migration_and_backup_roundtrip_with_legacy_backup(fertilizer):
    db,c,engine=fertilizer
    with engine.begin() as connection:
        for name in ['fertilization_applications','fertilization_plans','fertilization_soil_tests']:
            connection.execute(text('DROP TABLE '+name))
        add_fertilization_schema(connection);add_fertilization_schema(connection)
        assert connection.execute(text('SELECT count(*) FROM beds')).scalar()==2
    soil(c);pid=plan(c).json()['id'];confirm(c,pid)
    c.post(f'/api/fertilization/plans/{pid}/complete',json={'applied_on':str(date.today())})
    raw,_=create_backup_bytes(db)
    parsed=parse_backup(raw)
    assert len(parsed.rows_by_table['fertilization_applications'])==1
    restore_parsed_backup(db,parsed)
    assert overview(c)['declared_totals']['n']['known_kg']==.2
    envelope=json.loads(raw)
    for name in ['fertilization_soil_tests','fertilization_plans','fertilization_applications']:
        del envelope['payload']['tables'][name]
    envelope['payload']['table_count']=len(envelope['payload']['tables'])
    envelope['payload']['record_count']=sum(len(rows) for rows in envelope['payload']['tables'].values())
    envelope['checksum_sha256']=hashlib.sha256(canonical_json(envelope['payload'])).hexdigest()
    legacy=parse_backup(canonical_json(envelope))
    assert legacy.rows_by_table['fertilization_applications']==[]

    restore_parsed_backup(db,legacy)
    assert overview(c)["applications"]==[]
