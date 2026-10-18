import json
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.dynamic_dtm import DTM_COLUMNS, store_prediction
from app.models import IrrigationCropProfile
from test_dynamic_dtm import climate, series
from test_irrigation import CP
from test_irrigation_planning import configure
from test_succession import setup


@pytest.mark.parametrize('record_type', ['plans', 'plantings'])
@pytest.mark.parametrize('compatible', [False, True])
def test_weather_recalculation_checks_shared_valve_atomically(setup, record_type, compatible):
    from app.main import update_dynamic_dtm
    db, beds, variety, planting, plan, _ = setup
    configure(db, beds, [variety.crop_id])
    record = plan(start=0) if record_type == 'plans' else planting()
    record.sowing_date = date.today()
    record.expected_harvest_date = date.today() + timedelta(days=30)
    store_prediction(record, variety)
    peer = plan(bed=1, start=0)
    store_prediction(peer, variety)
    if compatible:
        profile = db.scalar(select(IrrigationCropProfile))
        profile.parameters = json.dumps({**CP, 'kc_initial': 1, 'kc_mid': 1, 'kc_late': 1})
    db.commit()
    before = {name: getattr(record, name) for name in DTM_COLUMNS}
    peer_before = peer.dynamic_dtm_explanation
    planned_date = record.expected_harvest_date
    payload = climate(series(15, start=date.today(), kind='forecast'))
    if compatible:
        result = update_dynamic_dtm(record_type, record.id, payload, db)
        assert result['dynamic_dtm']['method'] == 'gdd'
        assert record.dynamic_dtm_days == 10
        assert record.dynamic_dtm_initial_snapshot == before['dynamic_dtm_initial_snapshot']
    else:
        with pytest.raises(HTTPException) as error:
            update_dynamic_dtm(record_type, record.id, payload, db)
        assert error.value.status_code == 409 and 'Skupni ventil' in error.value.detail
        db.refresh(record)
        assert {name: getattr(record, name) for name in DTM_COLUMNS} == before
    assert record.expected_harvest_date == planned_date
    assert peer.dynamic_dtm_explanation == peer_before
    assert not db.dirty
