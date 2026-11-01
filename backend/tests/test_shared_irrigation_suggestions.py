import json
from datetime import date

import pytest
from sqlalchemy import select

from app.dynamic_dtm import store_prediction
from app.irrigation_planning import assess, load_context, suggestion_cycle
from app.models import IrrigationCropProfile
from test_irrigation import CP
from test_irrigation_planning import configure
from test_production_planner import other_crop
from test_succession import setup


@pytest.mark.parametrize('successor', [False, True])
@pytest.mark.parametrize('compatible', [False, True])
def test_suggestions_screen_shared_peer_without_writes(setup, successor, compatible):
    from app.main import planting_suggestions
    from app.schemas import PlantingSuggestionRequest
    db, beds, variety, _, plan, client = setup
    configure(db, beds, [variety.crop_id])
    peer = plan(bed=1, start=0)
    store_prediction(peer, variety)
    if not compatible:
        peer.predicted_harvest_start = peer.expected_harvest_date
    db.commit()
    if successor:
        result = client.get(f'/api/beds/{beds[0].id}/next-crop-suggestions', params={'start_date': str(date.today())})
        assert result.status_code == 200
        report = result.json()
        assert bool(report['suggestions']) == compatible
    else:
        report = planting_suggestions(PlantingSuggestionRequest(crop_id=variety.crop_id,
            variety_id=variety.id, sowing_date=date.today()), db)
        assert (beds[0].id in {r['bed_id'] for r in report['recommended_beds']}) == compatible
    assert bool(report['irrigation_excluded']) != compatible
    assert not db.new and not db.dirty


def test_joint_ideas_check_previously_selected_crops(setup):
    from app.main import planting_suggestions
    from app.schemas import PlantingSuggestionRequest
    db, beds, variety, _, _, _ = setup
    crop, other = other_crop(db)
    configure(db, beds, [variety.crop_id, crop.id])
    profile = db.scalar(select(IrrigationCropProfile).where(IrrigationCropProfile.crop_id == crop.id))
    profile.parameters = json.dumps({**CP, 'kc_initial': 1.5, 'kc_mid': 1.5, 'kc_late': 1.5})
    db.commit()
    report = planting_suggestions(PlantingSuggestionRequest(crop_id=variety.crop_id,
        variety_id=variety.id, sowing_date=date.today()), db)
    shared = [r for r in report['planting_ideas'] if r['bed_id'] in {b.id for b in beds[:2]}]
    assert len(shared) == 2
    varieties = {variety.id: variety, other.id: other}
    cycles = [suggestion_cycle(r['bed_id'], r['crop_id'], varieties[r['variety_id']], date.today()) for r in shared]
    assert assess(cycles[0], cycles[1:], load_context(db, 1))['compatible']
    assert not db.new and not db.dirty
