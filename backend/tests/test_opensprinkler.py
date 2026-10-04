import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Bed, Farm, IrrigationDailyReport
from test_irrigation import irrigation, BP, CP, payload

STATION="switch.greda_1_station_enabled"

def prepare(client, **bed_changes):
    assert client.put("/api/irrigation/beds/1",json={**BP,"flow_l_min":10,
                      "opensprinkler_station_entity":STATION,**bed_changes}).status_code==200
    assert client.put("/api/irrigation/daily",json=payload()).status_code==200

def export(client,day=None):
    r=client.get(f"/api/irrigation/opensprinkler?day={day or date.today()}")
    assert r.status_code==200
    return r.json()

def test_manual_draft_correct_action_seconds_and_no_writes(irrigation):
    db,c,_=irrigation;prepare(c)
    row=db.scalar(select(IrrigationDailyReport));before=row.report
    r=export(c);draft=r["rows"][0]
    assert not r["automatic_execution"] and r["requires_manual_review"]
    assert draft["status"]=="draft" and draft["run_seconds"]==1125
    assert draft["action"]=={"action":"opensprinkler.run_station","target":{"entity_id":STATION},
                             "data":{"run_seconds":1125,"queue_option":"append"}}
    assert "run_seconds: 1125" in draft["yaml"] and "switch.turn_on" not in draft["yaml"]
    assert row.report==before and not db.dirty and not db.new

@pytest.mark.parametrize("changes",[{"opensprinkler_station_entity":None},{"flow_l_min":None},{"max_run_seconds":100}])
def test_missing_mapping_flow_and_duration_limit_block(irrigation,changes):
    _,c,_=irrigation;prepare(c,**changes);r=export(c)["rows"][0]
    assert r["status"]=="blocked" and r["action"] is None and r["yaml"] is None

@pytest.mark.parametrize("hours",[7,-1])
def test_old_and_future_calculation_block(irrigation,hours):
    db,c,_=irrigation;prepare(c);row=db.scalar(select(IrrigationDailyReport))
    r=json.loads(row.report);r["calculated_at"]=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat()
    row.report=json.dumps(r);db.commit()
    assert export(c)["rows"][0]["status"]=="blocked"

def test_previous_day_is_not_actionable(irrigation):
    _,c,_=irrigation;prepare(c)
    yesterday=date.today()-timedelta(days=1)
    c.put("/api/irrigation/daily",json=payload(day=str(yesterday)))
    assert export(c,yesterday)["rows"][0]["status"]=="blocked"

@pytest.mark.parametrize("change",["crop","bed","area"])
def test_changed_profiles_and_area_require_recalculation(irrigation,change):
    db,c,_=irrigation;prepare(c)
    if change=="crop":c.put("/api/irrigation/crops/1",json={**CP,"kc_mid":1.1})
    elif change=="bed":c.put("/api/irrigation/beds/1",json={**BP,"flow_l_min":11,"opensprinkler_station_entity":STATION})
    else:db.get(Bed,1).length_m=20;db.commit()
    assert export(c)["rows"][0]["status"]=="blocked"
    c.put("/api/irrigation/daily",json=payload())
    assert export(c)["rows"][0]["status"]=="draft"

def test_duplicate_station_blocks_and_other_farm_does_not(irrigation):
    db,c,_=irrigation;prepare(c)
    db.add(Bed(id=3,farm_id=1,name="A2",width_m=1,length_m=10,status="empty"));db.commit()
    c.put("/api/irrigation/beds/3",json={**BP,"opensprinkler_station_entity":STATION})
    assert export(c)["rows"][0]["status"]=="blocked"
    c.put("/api/irrigation/beds/3",json=BP)
    from app.models import IrrigationBedProfile
    db.add(IrrigationBedProfile(farm_id=2,bed_id=2,parameters=json.dumps({**BP,"opensprinkler_station_entity":STATION})));db.commit()
    assert export(c)["rows"][0]["status"]=="draft"

def test_sensor_stales_after_save_and_is_rechecked(irrigation):
    db,c,_=irrigation;prepare(c)
    row=db.scalar(select(IrrigationDailyReport));r=json.loads(row.report)
    r["inputs"].update(soil_moisture_pct=30,sensor_observed_at=(datetime.now(timezone.utc)-timedelta(hours=7)).isoformat())
    row.report=json.dumps(r);db.commit()
    assert export(c)["rows"][0]["status"]=="blocked"

def test_hold_and_missing_data_have_no_actions(irrigation):
    _,c,_=irrigation;prepare(c)
    for data in (payload(initial_depletion_mm=0,eto_mm=0),payload(eto_mm=None)):
        c.put("/api/irrigation/daily",json=data)
        assert export(c)["rows"][0]["action"] is None

@pytest.mark.parametrize("entity",["switch.x\nmalicious: true","light.greda","switch.x-y","switch.","switch.a b"])
def test_invalid_entity_ids(irrigation,entity):
    _,c,_=irrigation;assert c.put("/api/irrigation/beds/1",json={**BP,"opensprinkler_station_entity":entity}).status_code==422

def test_legacy_profile_defaults_and_no_saved_reports(irrigation):
    db,c,_=irrigation
    from app.models import IrrigationBedProfile
    row=db.scalar(select(IrrigationBedProfile));row.parameters=json.dumps(BP);db.commit()
    bp=c.get("/api/irrigation/profiles").json()["beds"][0]
    assert bp["opensprinkler_station_entity"] is None and bp["max_run_seconds"]==3600
    assert export(c)["rows"]==[]
