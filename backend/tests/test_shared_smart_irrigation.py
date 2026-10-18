from datetime import date, datetime, timedelta, timezone

import pytest

from app import irrigation_routes as routes
from app.models import Bed, Planting, Variety
from test_irrigation import BP, irrigation


ZONE = 'sensor.smart_irrigation_shared'
STATION = 'switch.shared_valve'


@pytest.fixture
def shared(irrigation, monkeypatch, tmp_path):
    db, client, _ = irrigation
    monkeypatch.setenv('GROWMASTER_DATA_ROOT', str(tmp_path))
    monkeypatch.setattr(routes, 'home_assistant_config', lambda: ('http://ha.test', 'test-token'))
    db.add(Variety(id=1, crop_id=1, name='Test', days_to_harvest=40,
                   days_spring=40, days_summer=40, days_autumn=40, days_winter=40))
    db.add(Bed(id=3, farm_id=1, name='A2', width_m=1, length_m=10, status='growing'))
    for bid in (1, 3):
        db.add(Planting(farm_id=1, bed_id=bid, crop_id=1, variety_id=1,
                       sowing_date=date.today()-timedelta(days=10),
                       expected_harvest_date=date.today()+timedelta(days=30), status='active'))
    db.commit()
    profile = {**BP, 'valve_mode': 'shared', 'smart_irrigation_entity': ZONE,
               'opensprinkler_station_entity': STATION}
    for bid in (1, 3):
        assert client.put(f'/api/irrigation/beds/{bid}', json=profile).status_code == 200
    state = {'state': '300', 'attributes': {'multiplier': 1, 'size': 20, 'throughput': 4,
             'size_unit': 'm²', 'throughput_unit': 'l/min', 'unit_of_measurement': 'seconds',
             'last_calculated': datetime.now(timezone.utc).isoformat()},
             'last_updated': datetime.now(timezone.utc).isoformat()}
    calls = []
    class Response:
        status_code = 200
        def json(self): return state
    class HA:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, **kwargs):
            calls.append(('get', url, None))
            return Response()
        def post(self, url, **kwargs):
            calls.append(('post', url, kwargs['json']))
            if state.get('fail_post'):
                raise routes.httpx.ReadTimeout('uncertain')
            return Response()
    monkeypatch.setattr(routes.httpx, 'Client', HA)
    return db, client, state, calls, profile


def readiness(client):
    response = client.get(f'/api/irrigation/daily-readiness?day={date.today()}')
    assert response.status_code == 200
    return response.json()


def test_one_sensor_one_group_run_without_separate_daily_reports(shared):
    _, client, _, calls, _ = shared
    result = readiness(client)
    assert len(calls) == 1 and calls[0][0] == 'get'
    assert all(r['ready'] and r['action'] is None for r in result['rows'])
    group = result['valve_groups'][0]
    assert group['status'] == 'draft' and group['run_seconds'] == 300
    assert group['area_m2'] == 20 and group['flow_l_min'] == 4
    assert group['estimated_litres'] == 20
    assert group['bed_water_estimates'] == [{'bed_id': 1, 'litres': 10}, {'bed_id': 3, 'litres': 10}]


def test_manual_kc_sends_once_and_waits_for_real_recalculation(shared):
    _, client, state, calls, _ = shared
    preview = client.get(f'/api/irrigation/smart-irrigation?day={date.today()}').json()
    assert len(preview['rows']) == 1 and preview['rows'][0]['bed_ids'] == [1, 3]
    response = client.post(f'/api/irrigation/home-assistant/smart-irrigation?day={date.today()}')
    assert response.status_code == 200 and len(response.json()['sent']) == 1
    assert len([c for c in calls if c[0] == 'post']) == 1
    state['last_updated'] = datetime.now(timezone.utc).isoformat()
    assert readiness(client)['valve_groups'][0]['action'] is None
    state['attributes']['last_calculated'] = datetime.now(timezone.utc).isoformat()
    assert readiness(client)['valve_groups'][0]['status'] == 'draft'


@pytest.mark.parametrize('change', ['area', 'flow', 'units', 'stale', 'timestamp', 'duration', 'method'])
def test_invalid_shared_si_state_never_yields_valve_action(shared, change):
    _, client, state, _, _ = shared
    attrs = state['attributes']
    if change == 'area': attrs['size'] = 10
    if change == 'flow': attrs['throughput'] = 2
    if change == 'units': attrs.pop('throughput_unit')
    if change == 'stale': attrs['last_calculated'] = (datetime.now(timezone.utc)-timedelta(hours=7)).isoformat()
    if change == 'timestamp': attrs.pop('last_calculated')
    if change == 'duration': state['state'] = '10000'
    if change == 'method': attrs['input_method'] = 'direct'
    result = readiness(client)
    assert result['valve_groups'][0]['action'] is None
    assert all(not r['ready'] and r['action'] is None for r in result['rows'])


@pytest.mark.parametrize('change', ['phase', 'empty', 'station', 'mode', 'flow'])
def test_incompatible_members_block_kc_and_valve(shared, change):
    db, client, _, _, profile = shared
    if change in {'phase', 'empty'}:
        planting = db.query(Planting).filter_by(bed_id=3).one()
        if change == 'empty': planting.status = 'completed'
        else: planting.sowing_date = date.today()-timedelta(days=1)
        db.commit()
    else:
        key, value = {'station': ('opensprinkler_station_entity', 'switch.other'),
                      'mode': ('valve_mode', 'individual'), 'flow': ('flow_l_min', None)}[change]
        client.put('/api/irrigation/beds/3', json={**profile, key: value})
    preview = client.get(f'/api/irrigation/smart-irrigation?day={date.today()}').json()
    assert all(row['action'] is None for row in preview['rows'])
    result = readiness(client)
    assert all(row['action'] is None and not row['ready'] for row in result['rows'])
    assert all(group['action'] is None for group in result['valve_groups'])


@pytest.mark.parametrize('timeout', [False, True])
def test_automatic_shared_valve_submitted_only_once_even_after_timeout(shared, timeout):
    db, _, state, calls, _ = shared
    routes._write_automatic_state({'enabled': True, 'run_after_local_time': '00:00', 'runs': {}})
    state['fail_post'] = timeout
    first = routes.automatic_irrigation_tick(db)
    second = routes.automatic_irrigation_tick(db)
    assert first['started'] == (0 if timeout else 1) and second['started'] == 0
    posts = [call for call in calls if call[0] == 'post']
    assert len(posts) == 1 and posts[0][2]['entity_id'] == STATION


def test_automatic_shared_kc_updates_once_before_any_valve_run(shared):
    db, _, state, calls, _ = shared
    routes._write_automatic_state({'enabled': True, 'run_after_local_time': '00:00', 'runs': {}})
    state['attributes']['multiplier'] = .5
    first = routes.automatic_irrigation_tick(db)
    assert first['updated_zones'] == 1 and first['started'] == 0
    assert len([c for c in calls if c[0] == 'post']) == 1
    state['attributes']['multiplier'] = 1
    assert routes.automatic_irrigation_tick(db)['started'] == 0
    state['attributes']['last_calculated'] = datetime.now(timezone.utc).isoformat()
    assert routes.automatic_irrigation_tick(db)['started'] == 1


@pytest.mark.parametrize('change', ['zero', 'dose', 'conflict'])
def test_automatic_shared_group_blocks_without_any_post(shared, change):
    db, client, state, calls, profile = shared
    routes._write_automatic_state({'enabled': True, 'run_after_local_time': '00:00', 'runs': {}})
    if change == 'zero': state['state'] = '0'
    if change == 'dose':
        client.put('/api/irrigation/beds/3', json={**profile, 'max_application_mm': .1})
    if change == 'conflict':
        db.query(Planting).filter_by(bed_id=3).one().sowing_date = date.today()-timedelta(days=1)
        db.commit()
    assert routes.automatic_irrigation_tick(db)['started'] == 0
    assert not [call for call in calls if call[0] == 'post']
