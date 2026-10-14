import hashlib
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.backups import create_backup_bytes, parse_backup, canonical_json, restore_parsed_backup
from app.database import Base, get_db
from app import irrigation_routes
from app.irrigation_routes import router
from app.migrations import add_irrigation_schema
from app.models import Bed, Crop, Farm, IrrigationDailyReport, Planting, Variety

CP={"kc_initial":0.5,"kc_mid":1,"kc_late":0.8,"root_depth_m":0.3,"depletion_fraction":0.3,"source":"Testni profil"}
BP={"field_capacity_pct":30,"wilting_point_pct":15,"efficiency_pct":80,"flow_l_min":2,
    "max_application_mm":30,"sensor_dry_pct":25,"sensor_wet_pct":65,"source":"Umerjena testna tla"}

@pytest.fixture
def irrigation():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        db.add_all([Farm(id=1,name="Namakanje"),Farm(id=2,name="Tuja"),Crop(id=1,name="Solata",family="A",category="B")]);db.flush()
        db.add_all([Bed(id=1,farm_id=1,name="A1",width_m=1,length_m=10,status="empty"),Bed(id=2,farm_id=2,name="B",width_m=1,length_m=5,status="empty")]);db.commit()
        app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db
        with TestClient(app) as client:
            assert client.put("/api/irrigation/crops/1",json=CP).status_code==200
            assert client.put("/api/irrigation/beds/1",json=BP).status_code==200
            yield db,client,engine
    engine.dispose()

def payload(**changes):
    return {"bed_id":1,"crop_id":1,"day":str(date.today()),"stage":"mid","initial_depletion_mm":10,
            "eto_mm":5,"effective_rain_mm":0,"applied_irrigation_mm":0,"weather_source":"Ročni ET0",**changes}

def calc(client,**changes):
    return client.post("/api/irrigation/calculate",json=payload(**changes))

def test_balance_volume_time_and_no_preview_writes(irrigation):
    db,client,_=irrigation;r=calc(client).json()
    assert (r["taw_mm"],r["raw_mm"],r["depletion_mm"])==(45,13.5,15)
    assert (r["gross_mm"],r["litres"],r["minutes"])==(18.75,187.5,93.75)
    assert r["status"]=="irrigate" and r["remaining_depletion_mm"]==0
    assert not r["automatic_execution"] and r["confidence"]=="low"
    assert not db.dirty and not db.new and not db.scalar(select(IrrigationDailyReport))

def test_rain_and_applied_water_are_not_double_counted(irrigation):
    _,c,_=irrigation;r=calc(c,effective_rain_mm=2,applied_irrigation_mm=5).json()
    assert r["depletion_mm"]==9 and r["status"]=="hold" and r["litres"]==0
    assert calc(c,effective_rain_mm=100).json()["depletion_mm"]==0

def test_cap_preserves_remaining_deficit(irrigation):
    _,c,_=irrigation;c.put("/api/irrigation/beds/1",json={**BP,"max_application_mm":10})
    r=calc(c).json();assert r["gross_mm"]==10 and r["remaining_depletion_mm"]==7 and r["litres"]==100

def test_stage_and_no_flow(irrigation):
    _,c,_=irrigation;c.put("/api/irrigation/beds/1",json={**BP,"flow_l_min":None})
    assert calc(c,stage="initial").json()["etc_mm"]==2.5
    assert calc(c).json()["minutes"] is None

def test_missing_et0_is_not_zero(irrigation):
    _,c,_=irrigation;r=calc(c,eto_mm=None).json()
    assert r["status"]=="missing_data" and r["litres"] is None
    assert calc(c,eto_mm=0,initial_depletion_mm=0).json()["status"]=="hold"

def test_daily_readiness_lists_active_beds_and_missing_inputs(irrigation):
    db,c,_=irrigation
    db.add(Variety(id=1,crop_id=1,name="Solata",days_to_harvest=40,days_spring=40,
                   days_summer=35,days_autumn=45,days_winter=55))
    db.add(Planting(farm_id=1,bed_id=1,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),
                    expected_harvest_date=date.today()+timedelta(days=30),status="active"))
    db.commit()
    result=c.get(f"/api/irrigation/daily-readiness?day={date.today()}").json()
    assert result["active_beds"]==1 and result["ready_beds"]==0 and result["needs_attention"]==1
    assert result["rows"][0]["crop"]=="Solata" and not result["rows"][0]["ready"]
    assert result["rows"][0]["days_after_sowing"]==10 and result["rows"][0]["suggested_stage"]=="initial"
    assert result["rows"][0]["stage_requires_confirmation"]
    assert any("ni shranjenega izračuna" in reason for reason in result["rows"][0]["reasons"])
    assert not result["automatic_execution"]

def test_daily_readiness_without_soil_sensor_uses_smart_irrigation_mode(irrigation):
    db,c,_=irrigation
    db.add(Variety(id=1,crop_id=1,name="Solata",days_to_harvest=40,days_spring=40,
                   days_summer=35,days_autumn=45,days_winter=55))
    db.add(Planting(farm_id=1,bed_id=1,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),
                    expected_harvest_date=date.today()+timedelta(days=30),status="active"))
    db.commit()
    c.put("/api/irrigation/beds/1",json={**BP,"mode":"smart_irrigation","smart_irrigation_entity":"sensor.smart_irrigation_a1"})
    c.put("/api/irrigation/daily",json=payload())
    result=c.get(f"/api/irrigation/daily-readiness?day={date.today()}").json()
    assert result["rows"][0]["mode"]=="smart_irrigation"
    assert not any("senzor" in reason for reason in result["rows"][0]["reasons"])

def test_daily_readiness_with_soil_sensor_requires_fresh_sensor_read(irrigation,monkeypatch):
    db,c,_=irrigation
    db.add(Variety(id=1,crop_id=1,name="Solata",days_to_harvest=40,days_spring=40,
                   days_summer=35,days_autumn=45,days_winter=55))
    db.add(Planting(farm_id=1,bed_id=1,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),
                    expected_harvest_date=date.today()+timedelta(days=30),status="active"))
    db.commit()
    c.put("/api/irrigation/sensor-groups/1",json={"name":"WH51 1","entity_id":"sensor.wh51_group_1"})
    c.put("/api/irrigation/beds/1",json={**BP,"mode":"soil_sensor","wh51_group":1,"smart_irrigation_entity":"sensor.smart_irrigation_a1"})
    c.put("/api/irrigation/daily",json=payload(soil_moisture_pct=32,sensor_observed_at=datetime.now(timezone.utc).isoformat()))
    monkeypatch.delenv("HOME_ASSISTANT_URL",raising=False);monkeypatch.delenv("HOME_ASSISTANT_TOKEN",raising=False)
    result=c.get(f"/api/irrigation/daily-readiness?day={date.today()}").json()
    assert result["rows"][0]["mode"]=="soil_sensor" and not result["rows"][0]["ready"]
    assert any("Povezava Home Assistant" in reason for reason in result["rows"][0]["reasons"])

def test_wh51_daily_readiness_prepares_action_for_the_bed_valve(irrigation,monkeypatch):
    db,c,_=irrigation
    db.add(Variety(id=1,crop_id=1,name="Solata",days_to_harvest=40,days_spring=40,days_summer=35,days_autumn=45,days_winter=55))
    db.add(Planting(farm_id=1,bed_id=1,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),
                    expected_harvest_date=date.today()+timedelta(days=30),status="active"))
    db.commit()
    c.put("/api/irrigation/sensor-groups/1",json={"name":"WH51 1","entity_id":"sensor.wh51_group_1"})
    c.put("/api/irrigation/beds/1",json={**BP,"mode":"soil_sensor","wh51_group":1,"irrigation_zone":"zone_1",
        "smart_irrigation_entity":"sensor.smart_irrigation_a1","opensprinkler_station_entity":"switch.bed_1_valve",
        "max_run_seconds":10000})
    monkeypatch.setenv("HOME_ASSISTANT_URL","http://ha.local:8123");monkeypatch.setenv("HOME_ASSISTANT_TOKEN","token")
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs:[(None,None,None,None,("192.168.1.10",8123))])
    class Response:
        status_code=200
        def json(self):return {"state":"32","attributes":{"unit_of_measurement":"%"},"last_updated":datetime.now(timezone.utc).isoformat()}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,headers):assert url.endswith("sensor.wh51_group_1");return Response()
    monkeypatch.setattr(irrigation_routes.httpx,"Client",Client)
    c.put("/api/irrigation/daily",json=payload(soil_moisture_pct=32,sensor_observed_at=datetime.now(timezone.utc).isoformat()))
    row=c.get(f"/api/irrigation/daily-readiness?day={date.today()}").json()["rows"][0]
    assert row["ready"]
    assert row["action"]=={"action":"opensprinkler.run_station","target":{"entity_id":"switch.bed_1_valve"},
                            "data":{"run_seconds":5625,"queue_option":"append"}}
    assert row["planting_id"] and row["crop"]=="Solata"

def test_wh51_groups_limit_to_16_sensor_entities(irrigation):
    _,c,_=irrigation
    for group in range(1,17):
        assert c.put(f"/api/irrigation/sensor-groups/{group}",json={"name":f"WH51 {group}","entity_id":f"sensor.wh51_{group}"}).status_code==200
    assert c.put("/api/irrigation/sensor-groups/17",json={"name":"WH51 17","entity_id":"sensor.wh51_17"}).status_code==422

def test_multiple_beds_can_be_manually_assigned_to_same_wh51_group(irrigation):
    db,c,_=irrigation
    db.add(Bed(id=3,farm_id=1,name="A2",width_m=1,length_m=5,status="active"))
    db.commit()
    group=c.put("/api/irrigation/sensor-groups/1",json={"name":"WH51 pri solati","entity_id":"sensor.wh51_1"})
    assert group.status_code==200
    assert c.put("/api/irrigation/beds/1",json={**BP,"mode":"soil_sensor","wh51_group":1}).status_code==200
    assert c.put("/api/irrigation/beds/3",json={**BP,"mode":"soil_sensor","wh51_group":1}).status_code==200
    saved=c.get("/api/irrigation/profiles").json()
    assert len([profile for profile in saved["beds"] if profile.get("wh51_group")==1])==2
    assert saved["sensor_groups"]==[{"group_number":1,"name":"WH51 pri solati","entity_id":"sensor.wh51_1"}]

def test_readiness_shares_one_group_reading_across_assigned_beds(irrigation,monkeypatch):
    db,c,_=irrigation
    db.add_all([
        Bed(id=3,farm_id=1,name="A2",width_m=1,length_m=5,status="active"),
        Variety(id=1,crop_id=1,name="Solata",days_to_harvest=40,days_spring=40,days_summer=35,days_autumn=45,days_winter=55),
    ])
    db.flush()
    for bed_id in (1,3):
        db.add(Planting(farm_id=1,bed_id=bed_id,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),
                        expected_harvest_date=date.today()+timedelta(days=30),status="active"))
    db.commit()
    monkeypatch.setenv("HOME_ASSISTANT_URL","http://ha.local:8123");monkeypatch.setenv("HOME_ASSISTANT_TOKEN","token")
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs:[(None,None,None,None,("192.168.1.10",8123))])
    c.put("/api/irrigation/sensor-groups/1",json={"name":"WH51 skupina","entity_id":"sensor.wh51_1"})
    class Response:
        status_code=200
        def json(self):return {"state":"32","attributes":{"unit_of_measurement":"%"},"last_updated":datetime.now(timezone.utc).isoformat()}
    calls=[]
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,headers):calls.append(url);return Response()
    monkeypatch.setattr(irrigation_routes.httpx,"Client",Client)
    for bed_id in (1,3):
        c.put(f"/api/irrigation/beds/{bed_id}",json={**BP,"mode":"soil_sensor","wh51_group":1})
        c.put("/api/irrigation/daily",json=payload(bed_id=bed_id))
    result=c.get(f"/api/irrigation/daily-readiness?day={date.today()}").json()
    assert len(calls)==3  # daily saves read independently; shared beds use one readiness read
    assert all(row["wh51_group"]==1 and row["sensor_group_beds"]==2 for row in result["rows"])

def test_calculate_reads_wh51_group_and_saves_sensor_measurement(irrigation,monkeypatch):
    _,c,_=irrigation
    c.put("/api/irrigation/sensor-groups/1",json={"name":"WH51 skupina","entity_id":"sensor.wh51_1"})
    c.put("/api/irrigation/beds/1",json={**BP,"mode":"soil_sensor","wh51_group":1,"smart_irrigation_entity":"sensor.smart_irrigation_a1"})
    monkeypatch.setenv("HOME_ASSISTANT_URL","http://ha.local:8123");monkeypatch.setenv("HOME_ASSISTANT_TOKEN","token")
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs:[(None,None,None,None,("192.168.1.10",8123))])
    class Response:
        status_code=200
        def json(self):return {"state":"32","attributes":{"unit_of_measurement":"%"},"last_updated":datetime.now(timezone.utc).isoformat()}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,headers):assert url.endswith("/api/states/sensor.wh51_1");return Response()
    monkeypatch.setattr(irrigation_routes.httpx,"Client",Client)
    result=c.put("/api/irrigation/daily",json=payload()).json()
    assert result["inputs"]["soil_moisture_pct"]==32
    assert result["wh51"]["group_number"]==1 and result["wh51"]["entity_id"]=="sensor.wh51_1"

def test_smart_irrigation_mode_calculates_without_wh51_or_ha(irrigation,monkeypatch):
    _,c,_=irrigation
    monkeypatch.delenv("HOME_ASSISTANT_URL",raising=False);monkeypatch.delenv("HOME_ASSISTANT_TOKEN",raising=False)
    c.put("/api/irrigation/beds/1",json={**BP,"mode":"smart_irrigation","wh51_group":None,
        "smart_irrigation_entity":"sensor.smart_irrigation_a1"})
    result=c.put("/api/irrigation/daily",json=payload()).json()
    assert result["status"]=="irrigate"
    assert "wh51" not in result and result["inputs"]["soil_moisture_pct"] is None

@pytest.mark.parametrize("seconds,decision,run_seconds",[(0,"hold",None),(125.2,"irrigate",126)])
def test_smart_irrigation_daily_plan_reads_seconds_and_prepares_manual_station_draft(irrigation,monkeypatch,seconds,decision,run_seconds):
    db,c,_=irrigation
    db.add(Variety(id=1,crop_id=1,name="Solata",days_to_harvest=40,days_spring=40,days_summer=35,days_autumn=45,days_winter=55))
    db.add(Planting(farm_id=1,bed_id=1,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),
                    expected_harvest_date=date.today()+timedelta(days=30),status="active"))
    db.commit()
    c.put("/api/irrigation/beds/1",json={**BP,"mode":"smart_irrigation","smart_irrigation_entity":"sensor.smart_irrigation_a1",
        "opensprinkler_station_entity":"switch.station_a1"})
    monkeypatch.setenv("HOME_ASSISTANT_URL","http://ha.local:8123");monkeypatch.setenv("HOME_ASSISTANT_TOKEN","token")
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs:[(None,None,None,None,("192.168.1.10",8123))])
    class Response:
        status_code=200
        def json(self):return {"state":str(seconds),"attributes":{"unit_of_measurement":"seconds","last_calculated":datetime.now(timezone.utc).isoformat()},"last_updated":datetime.now(timezone.utc).isoformat()}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,headers):assert url.endswith("sensor.smart_irrigation_a1");return Response()
    monkeypatch.setattr(irrigation_routes.httpx,"Client",Client)
    result=c.get(f"/api/irrigation/daily-readiness?day={date.today()}").json()["rows"][0]
    assert result["decision"]==decision and result["smart_irrigation_seconds"]==seconds
    if run_seconds is None:
        assert result["action"] is None
    else:
        assert result["action"]["data"]["run_seconds"]==run_seconds
        assert result["action"]["action"]=="opensprinkler.run_station"

def test_daily_readiness_blocks_if_saved_crop_differs_from_active_crop(irrigation):
    db,c,_=irrigation
    db.add(Variety(id=1,crop_id=1,name="Solata",days_to_harvest=40,days_spring=40,
                   days_summer=35,days_autumn=45,days_winter=55))
    db.add(Planting(farm_id=1,bed_id=1,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),
                    expected_harvest_date=date.today()+timedelta(days=30),status="active"))
    db.commit()
    c.put("/api/irrigation/daily",json=payload())
    db.query(Planting).filter(Planting.bed_id==1).update({Planting.status:"completed"})
    db.commit()
    db.add(Crop(id=2,name="Koriander",family="C",category="B"))
    db.add(Variety(id=2,crop_id=2,name="Nova",days_to_harvest=40,days_spring=40,
                   days_summer=35,days_autumn=45,days_winter=55))
    db.flush()
    db.add(Planting(farm_id=1,bed_id=1,crop_id=2,variety_id=2,sowing_date=date.today(),
                    expected_harvest_date=date.today()+timedelta(days=40),status="active"))
    db.commit()
    result=c.get(f"/api/irrigation/daily-readiness?day={date.today()}").json()
    assert not result["rows"][0]["ready"]
    assert any("ne ustreza" in reason for reason in result["rows"][0]["reasons"])

def test_water_ledger_carries_depletion_between_days_and_validates_sequence(irrigation):
    _,c,_=irrigation
    day1=date.today()-timedelta(days=1)
    c.put("/api/irrigation/daily",json=payload(day=str(day1)))
    saved=c.put("/api/irrigation/water-ledger",json={"bed_id":1,"day":str(day1),
        "opening_depletion_mm":10,"etc_mm":5,"effective_rain_mm":1,"applied_irrigation_mm":2,"source":"Ročni pregled"})
    assert saved.status_code==200 and saved.json()["closing_depletion_mm"]==12.4
    c.put("/api/irrigation/daily",json=payload())
    mismatch=c.put("/api/irrigation/water-ledger",json={"bed_id":1,"day":str(date.today()),
        "opening_depletion_mm":12.4,"etc_mm":0,"effective_rain_mm":0,"applied_irrigation_mm":0,"source":"Ročni pregled"})
    assert mismatch.status_code==409
    bad=c.put("/api/irrigation/water-ledger",json={"bed_id":1,"day":str(date.today()),
        "opening_depletion_mm":10,"etc_mm":5,"effective_rain_mm":0,"applied_irrigation_mm":0,"source":"Ročni pregled"})
    assert bad.status_code==409
    good=c.put("/api/irrigation/water-ledger",json={"bed_id":1,"day":str(date.today()),
        "opening_depletion_mm":12.4,"etc_mm":5,"effective_rain_mm":0,"applied_irrigation_mm":0,"source":"Ročni pregled"})
    assert good.status_code==200 and good.json()["closing_depletion_mm"]==17.4
    assert len(c.get(f"/api/irrigation/water-ledger?bed_id=1&through={date.today()}").json()["rows"])==2

@pytest.mark.parametrize("changes",[{"soil_moisture_pct":80},{"soil_moisture_pct":10,"initial_depletion_mm":0,"eto_mm":0}])
def test_sensor_disagreement_blocks_quantity(irrigation,changes):
    _,c,_=irrigation;r=calc(c,sensor_observed_at=datetime.now(timezone.utc).isoformat(),**changes).json()
    assert r["status"]=="review" and r["litres"] is None

@pytest.mark.parametrize("hours",[-1,7])
def test_future_and_stale_sensor_block(irrigation,hours):
    _,c,_=irrigation;r=calc(c,soil_moisture_pct=30,sensor_observed_at=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat()).json()
    assert r["status"]=="review" and r["gross_mm"] is None

def test_uncalibrated_sensor_and_historical_sensor_review(irrigation):
    _,c,_=irrigation;c.put("/api/irrigation/beds/1",json={**BP,"sensor_dry_pct":None,"sensor_wet_pct":None})
    r=calc(c,soil_moisture_pct=30,sensor_observed_at=datetime.now(timezone.utc).isoformat()).json()
    assert r["status"]=="review"
    r=calc(c,day=str(date.today()-timedelta(days=1)),soil_moisture_pct=30,sensor_observed_at=datetime.now(timezone.utc).isoformat()).json()
    assert r["status"]=="review"

@pytest.mark.parametrize("change",[{"eto_mm":-1},{"eto_mm":31},{"eto_mm":"NaN"},{"stage":"unknown"},
    {"initial_depletion_mm":46},{"day":str(date.today()+timedelta(days=1))},{"soil_moisture_pct":10},
    {"sensor_observed_at":"2026-01-01T12:00:00"},{"weather_source":" "},{"unknown":1}])
def test_invalid_daily_inputs(irrigation,change):
    _,c,_=irrigation;assert calc(c,**change).status_code==422

@pytest.mark.parametrize("change",[{"wilting_point_pct":30},{"efficiency_pct":0},{"flow_l_min":0},
    {"sensor_dry_pct":70},{"sensor_wet_pct":None},{"source":""}])
def test_invalid_bed_profile(irrigation,change):
    _,c,_=irrigation;assert c.put("/api/irrigation/beds/1",json={**BP,**change}).status_code==422

def test_invalid_smart_irrigation_entity_is_rejected(irrigation):
    _,c,_=irrigation
    assert c.put("/api/irrigation/beds/1",json={**BP,"smart_irrigation_entity":"switch.zone_1"}).status_code==422

def test_smart_irrigation_draft_uses_current_crop_and_does_not_run_valves(irrigation):
    db,c,_=irrigation
    db.add(Variety(id=1,crop_id=1,name="Testna sorta",days_to_harvest=40,days_spring=40,
                   days_summer=35,days_autumn=45,days_winter=55))
    db.add(Planting(farm_id=1,bed_id=1,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),
                    expected_harvest_date=date.today()+timedelta(days=30),status="active"))
    db.commit()
    assert c.put("/api/irrigation/beds/1",json={**BP,"smart_irrigation_entity":"sensor.smart_irrigation_a1"}).status_code==200
    c.put("/api/irrigation/daily",json=payload(stage="initial"))
    result=c.get(f"/api/irrigation/smart-irrigation?day={date.today()}").json()
    row=result["rows"][0]
    assert row["status"]=="draft"
    assert row["action"]=={"action":"smart_irrigation.set_multiplier",
                           "target":{"entity_id":"sensor.smart_irrigation_a1"},
                           "data":{"new_multiplier_value":0.5}}
    assert not result["automatic_execution"] and result["requires_manual_review"]
    assert "opensprinkler.run_station" not in row["yaml"]

def test_smart_irrigation_draft_blocks_if_crop_is_not_active(irrigation):
    _,c,_=irrigation
    c.put("/api/irrigation/beds/1",json={**BP,"smart_irrigation_entity":"sensor.smart_irrigation_a1"})
    c.put("/api/irrigation/daily",json=payload())
    row=c.get(f"/api/irrigation/smart-irrigation?day={date.today()}").json()["rows"][0]
    assert row["status"]=="blocked"
    assert any("ni več trenutna aktivna zasaditev" in reason for reason in row["reasons"])

def test_smart_irrigation_draft_blocks_a_zone_shared_by_multiple_beds(irrigation):
    db,c,_=irrigation
    db.add(Variety(id=1,crop_id=1,name="Testna sorta",days_to_harvest=40,days_spring=40,
                   days_summer=35,days_autumn=45,days_winter=55))
    db.add(Bed(id=3,farm_id=1,name="A2",width_m=1,length_m=10,status="active"))
    db.add_all([
        Planting(farm_id=1,bed_id=1,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),expected_harvest_date=date.today()+timedelta(days=30),status="active"),
        Planting(farm_id=1,bed_id=3,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),expected_harvest_date=date.today()+timedelta(days=30),status="active"),
    ])
    db.commit()
    zone="sensor.smart_irrigation_shared"
    c.put("/api/irrigation/beds/1",json={**BP,"smart_irrigation_entity":zone})
    c.put("/api/irrigation/beds/3",json={**BP,"smart_irrigation_entity":zone})
    c.put("/api/irrigation/daily",json=payload())
    second={**payload(),"bed_id":3}
    c.put("/api/irrigation/daily",json=second)
    rows=c.get(f"/api/irrigation/smart-irrigation?day={date.today()}").json()["rows"]
    assert len(rows)==2 and all(row["status"]=="blocked" for row in rows)
    assert all(any("več gredic" in reason for reason in row["reasons"]) for row in rows)

def test_home_assistant_status_does_not_expose_credentials(irrigation,monkeypatch):
    _,c,_=irrigation
    monkeypatch.setenv("HOME_ASSISTANT_URL","http://ha.local:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN","secret-value")
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs: [(None,None,None,None,("192.168.1.10",8123))])
    result=c.get("/api/irrigation/home-assistant/status").json()
    assert result["configured"] and "secret-value" not in json.dumps(result)

def test_home_assistant_app_config_is_encrypted_and_never_returned(irrigation,monkeypatch,tmp_path):
    _,c,_=irrigation
    monkeypatch.setenv("GROWMASTER_DATA_ROOT",str(tmp_path))
    monkeypatch.delenv("HOME_ASSISTANT_URL",raising=False)
    monkeypatch.delenv("HOME_ASSISTANT_TOKEN",raising=False)
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs: [(None,None,None,None,("192.168.1.10",8123))])
    response=c.put("/api/irrigation/home-assistant/config",json={"url":"http://ha.local:8123/","token":"very-secret-ha-token"})
    assert response.status_code==200
    assert response.json()["configured"] and "very-secret-ha-token" not in response.text
    status=c.get("/api/irrigation/home-assistant/status")
    assert status.status_code==200
    assert status.json()=={"configured":True,"url":"http://ha.local:8123","token_configured":True,
                           "source":"application","automatic_execution":False,
                           "note":"Žeton je shranjen šifrirano na strežniku GrowMaster; API ga nikoli ne vrne."}
    config_file=tmp_path/"secrets"/"home-assistant.json"
    key_file=tmp_path/"secrets"/"home-assistant.key"
    assert config_file.exists() and key_file.exists()
    assert "very-secret-ha-token" not in config_file.read_text()
    assert irrigation_routes.read_stored_home_assistant_config()["token"]=="very-secret-ha-token"
    cleared=c.delete("/api/irrigation/home-assistant/config")
    assert cleared.status_code==200 and not cleared.json()["configured"]
    assert not config_file.exists()

def test_home_assistant_config_requires_token_on_first_save(irrigation,monkeypatch,tmp_path):
    _,c,_=irrigation
    monkeypatch.setenv("GROWMASTER_DATA_ROOT",str(tmp_path))
    monkeypatch.delenv("HOME_ASSISTANT_URL",raising=False)
    monkeypatch.delenv("HOME_ASSISTANT_TOKEN",raising=False)
    response=c.put("/api/irrigation/home-assistant/config",json={"url":"http://192.168.1.10:8123","token":""})
    assert response.status_code==422 and not (tmp_path/"secrets"/"home-assistant.json").exists()

def test_home_assistant_config_does_not_echo_oversized_token(irrigation,monkeypatch,tmp_path):
    _,c,_=irrigation
    monkeypatch.setenv("GROWMASTER_DATA_ROOT",str(tmp_path))
    monkeypatch.delenv("HOME_ASSISTANT_URL",raising=False)
    monkeypatch.delenv("HOME_ASSISTANT_TOKEN",raising=False)
    secret="x"*8193
    response=c.put("/api/irrigation/home-assistant/config",json={"url":"http://192.168.1.10:8123","token":secret})
    assert response.status_code==422 and secret not in response.text

def test_home_assistant_config_rejects_embedded_credentials_and_query(irrigation,monkeypatch,tmp_path):
    _,c,_=irrigation
    monkeypatch.setenv("GROWMASTER_DATA_ROOT",str(tmp_path))
    for url in ("http://user:pass@ha.local:8123","http://ha.local:8123/?token=secret","ftp://ha.local"):
        response=c.put("/api/irrigation/home-assistant/config",json={"url":url,"token":"secret-value"})
        assert response.status_code==422

def test_home_assistant_not_configured_is_reported_without_network(irrigation,monkeypatch):
    _,c,_=irrigation
    monkeypatch.delenv("HOME_ASSISTANT_URL",raising=False)
    monkeypatch.delenv("HOME_ASSISTANT_TOKEN",raising=False)
    assert c.get("/api/irrigation/home-assistant/status").json()["configured"] is False
    assert c.post("/api/irrigation/home-assistant/test").status_code==503

def test_home_assistant_local_name_requires_resolution_from_backend(irrigation,monkeypatch):
    _,c,_=irrigation
    monkeypatch.setenv("HOME_ASSISTANT_URL","http://homeassistant.local:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN","secret-value")
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs: (_ for _ in ()).throw(irrigation_routes.socket.gaierror()))
    assert c.get("/api/irrigation/home-assistant/status").json()["configured"]
    response=c.post("/api/irrigation/home-assistant/test")
    assert response.status_code==503 and "LAN IP" in response.json()["detail"]

def test_home_assistant_test_checks_api_only(irrigation,monkeypatch):
    _,c,_=irrigation
    monkeypatch.setenv("HOME_ASSISTANT_URL","http://ha.local:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN","secret-value")
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs: [(None,None,None,None,("192.168.1.10",8123))])
    class Response:
        status_code=200
        def json(self): return {"message":"API running."}
    class Client:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def get(self,url,headers):
            assert url=="http://ha.local:8123/api/" and headers["Authorization"]=="Bearer secret-value"
            return Response()
    monkeypatch.setattr(irrigation_routes.httpx,"Client",Client)
    result=c.post("/api/irrigation/home-assistant/test").json()
    assert result["connected"] and not result["automatic_execution"]

def test_home_assistant_reads_only_explicit_sensor_entities(irrigation,monkeypatch):
    _,c,_=irrigation
    monkeypatch.setenv("HOME_ASSISTANT_URL","http://ha.local:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN","secret-value")
    monkeypatch.setenv("HOME_ASSISTANT_WEATHER_ENTITIES","sensor.outdoor_temperature,sensor.rain_today")
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs: [(None,None,None,None,("192.168.1.10",8123))])
    c.put("/api/irrigation/sensor-groups/1",json={"name":"WH51 1","entity_id":"sensor.wh51_group_1"})
    c.put("/api/irrigation/beds/1",json={**BP,"mode":"soil_sensor","wh51_group":1})
    seen=[]
    class Response:
        status_code=200
        def __init__(self,entity_id): self.entity_id=entity_id
        def json(self): return {"entity_id":self.entity_id,"state":"22.5","attributes":{"unit_of_measurement":"%"},"last_updated":datetime.now(timezone.utc).isoformat()}
    class Client:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def get(self,url,headers):
            entity_id=url.rsplit("/",1)[-1];seen.append(entity_id);return Response(entity_id)
    monkeypatch.setattr(irrigation_routes.httpx,"Client",Client)
    result=c.get("/api/irrigation/home-assistant/states").json()
    assert seen==["sensor.outdoor_temperature","sensor.rain_today","sensor.wh51_group_1"]
    assert all(item["available"] for item in result["entities"])
    assert not result["automatic_execution"]

def test_home_assistant_sensor_read_validates_numeric_and_freshness(irrigation,monkeypatch):
    _,c,_=irrigation
    monkeypatch.setenv("HOME_ASSISTANT_URL","http://ha.local:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN","secret-value")
    monkeypatch.setenv("HOME_ASSISTANT_WEATHER_ENTITIES","sensor.fresh,sensor.stale,sensor.text")
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs: [(None,None,None,None,("192.168.1.10",8123))])
    class Response:
        status_code=200
        def __init__(self,entity_id):self.entity_id=entity_id
        def json(self):
            value={"state":"unavailable","last_updated":datetime.now(timezone.utc).isoformat(),"attributes":{"unit_of_measurement":"mm"}}
            if self.entity_id.endswith("fresh"):value.update(state="3.2")
            if self.entity_id.endswith("stale"):value.update(state="1.0",last_updated=(datetime.now(timezone.utc)-timedelta(hours=7)).isoformat())
            if self.entity_id.endswith("text"):value.update(state="raining")
            return value
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,headers):return Response(url.rsplit("/",1)[-1])
    monkeypatch.setattr(irrigation_routes.httpx,"Client",Client)
    result=c.get("/api/irrigation/home-assistant/states").json()
    by_entity={item["entity_id"]:item for item in result["entities"]}
    assert by_entity["sensor.fresh"]["available"] and by_entity["sensor.fresh"]["numeric_value"]==3.2
    assert not by_entity["sensor.stale"]["available"] and not by_entity["sensor.stale"]["fresh"]
    assert not by_entity["sensor.text"]["available"] and by_entity["sensor.text"]["numeric_value"] is None
    assert result["numeric_summary_by_unit"]["mm"]["count"]==2

def test_home_assistant_sensor_read_blocks_invalid_weather_entity(irrigation,monkeypatch):
    _,c,_=irrigation
    monkeypatch.setenv("HOME_ASSISTANT_URL","http://ha.local:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN","secret-value")
    monkeypatch.setenv("HOME_ASSISTANT_WEATHER_ENTITIES","switch.rain")
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs: [(None,None,None,None,("192.168.1.10",8123))])
    assert c.get("/api/irrigation/home-assistant/states").status_code==503

def test_home_assistant_sends_only_safe_smart_irrigation_kc(irrigation,monkeypatch):
    db,c,_=irrigation
    db.add(Variety(id=1,crop_id=1,name="Testna sorta",days_to_harvest=40,days_spring=40,
                   days_summer=35,days_autumn=45,days_winter=55))
    db.add(Planting(farm_id=1,bed_id=1,crop_id=1,variety_id=1,sowing_date=date.today()-timedelta(days=10),
                    expected_harvest_date=date.today()+timedelta(days=30),status="active"))
    db.commit()
    monkeypatch.setenv("HOME_ASSISTANT_URL","http://ha.local:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN","secret-value")
    monkeypatch.setattr(irrigation_routes.socket,"getaddrinfo",lambda *args,**kwargs: [(None,None,None,None,("192.168.1.10",8123))])
    c.put("/api/irrigation/beds/1",json={**BP,"smart_irrigation_entity":"sensor.smart_irrigation_a1"})
    c.put("/api/irrigation/daily",json=payload(stage="initial"))
    calls=[]
    class Response:
        status_code=200
    class Client:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,url,headers,json):
            calls.append((url,json))
            assert headers["Authorization"]=="Bearer secret-value"
            return Response()
    monkeypatch.setattr(irrigation_routes.httpx,"Client",Client)
    result=c.post(f"/api/irrigation/home-assistant/smart-irrigation?day={date.today()}").json()
    assert calls==[("http://ha.local:8123/api/services/smart_irrigation/set_multiplier",
                    {"entity_id":"sensor.smart_irrigation_a1","new_multiplier_value":0.5})]
    assert len(result["sent"])==1 and not result["automatic_execution"]
    assert "Ventili niso bili zagnani" in result["note"]

def test_farm_scope_and_unknown_crop(irrigation):
    _,c,_=irrigation;assert calc(c,bed_id=2).status_code==404
    assert c.put("/api/irrigation/beds/2",json=BP).status_code==404
    assert calc(c,crop_id=999).status_code==404

def test_daily_upsert_and_profile_snapshot(irrigation):
    db,c,_=irrigation;c.put("/api/irrigation/daily",json=payload())
    c.put("/api/irrigation/daily",json=payload(eto_mm=6))
    assert len(list(db.scalars(select(IrrigationDailyReport))))==1
    c.put("/api/irrigation/crops/1",json={**CP,"kc_mid":0.5})
    rows=c.get(f"/api/irrigation/daily?day={date.today()}").json()["rows"]
    assert rows[0]["kc"]==1 and rows[0]["etc_mm"]==6

def test_backup_roundtrip_and_old_backup_without_new_tables(irrigation):
    db,c,_=irrigation;c.put("/api/irrigation/daily",json=payload())
    content,_=create_backup_bytes(db);parsed=parse_backup(content)
    assert len(parsed.rows_by_table["irrigation_daily_reports"])==1
    restore_parsed_backup(db,parsed)
    doc=json.loads(content)
    for name in ("irrigation_crop_profiles","irrigation_bed_profiles","irrigation_daily_reports"):
        doc["payload"]["tables"].pop(name)
    doc["payload"]["table_count"]-=3
    doc["payload"]["record_count"]-=3
    doc["checksum_sha256"]=hashlib.sha256(canonical_json(doc["payload"])).hexdigest()
    old=parse_backup(json.dumps(doc).encode())
    assert old.rows_by_table["irrigation_daily_reports"]==[]
    restore_parsed_backup(db,old)
    assert not db.scalar(select(IrrigationDailyReport))

def test_additive_migration_is_repeatable_and_preserves_beds(irrigation):
    _,_,engine=irrigation
    with engine.begin() as conn:
        for name in ("irrigation_daily_reports","irrigation_bed_profiles","irrigation_crop_profiles"):
            conn.execute(text("DROP TABLE "+name))
        add_irrigation_schema(conn);add_irrigation_schema(conn)
        assert conn.execute(text("SELECT count(*) FROM beds")).scalar()==2

def test_water_ledger_migration_is_repeatable(irrigation):
    _,_,engine=irrigation
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE irrigation_water_ledger"))
        from app.migrations import add_irrigation_water_ledger
        add_irrigation_water_ledger(conn);add_irrigation_water_ledger(conn)
        assert "closing_depletion_mm" in {col["name"] for col in __import__("sqlalchemy").inspect(conn).get_columns("irrigation_water_ledger")}
