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
from app.irrigation_routes import router
from app.migrations import add_irrigation_schema
from app.models import Bed, Crop, Farm, IrrigationDailyReport

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
