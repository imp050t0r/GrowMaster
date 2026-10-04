from datetime import date
import json
from types import SimpleNamespace as NS

import pytest

from app.harvest_comparison import comparison, harvest_report


def record(first=date(2026, 5, 23), **changes):
    snapshot = dict(reference_date="2026-05-01", reference_kind="transplant",
                    predicted_harvest_date="2026-05-21", predicted_harvest_start="2026-05-18",
                    predicted_harvest_end="2026-05-24", calculated_at="2026-04-01T10:00:00+00:00",
                    planned_harvest_date="2026-05-20")
    planting = NS(id=1, farm_id=1, crop=NS(name="Solata"), variety=NS(name="Test"),
                  bed=NS(name="17"), sowing_date=date(2026,4,15), status="completed",
                  completed_on=date(2026,6,1), expected_harvest_date=date(2026,5,29),
                  dynamic_dtm_initial_snapshot=json.dumps(snapshot),
                  dynamic_dtm_explanation='{"predicted_harvest_date":"2026-05-30"}',
                  harvests=[] if first is None else [NS(farm_id=1,harvest_date=first)])
    for key, value in changes.items():
        setattr(planting, key, value)
    return planting


def test_initial_snapshot_first_harvest_and_reference_are_preserved():
    p=record(); original=p.dynamic_dtm_initial_snapshot
    p.harvests += [NS(farm_id=1,harvest_date=date(2026,5,29)), NS(farm_id=2,harvest_date=date(2026,5,2))]
    row=comparison(p,today=date(2026,6,1))
    assert row["eligible"] and row["within_window"]
    assert row["prediction_error_days"] == 2 and row["planned_error_days"] == 3
    assert row["days_from_initial_reference"] == 22 and row["harvest_count"] == 2
    assert p.dynamic_dtm_initial_snapshot == original and p.expected_harvest_date == date(2026,5,29)


@pytest.mark.parametrize("snapshot", [None, "broken", "[]", "{}", '{"reference_date":null}'])
def test_missing_or_invalid_snapshot_does_not_invent_prediction(snapshot):
    assert not comparison(record(dynamic_dtm_initial_snapshot=snapshot))["eligible"]


def test_completion_is_not_harvest():
    row=comparison(record(first=None))
    assert row["first_harvest_date"] is None and not row["eligible"]


@pytest.mark.parametrize("first", [date(2026,4,1), date(2026,5,1),date(2026,6,2),date(2027,1,1)])
def test_invalid_harvest_dates_are_excluded(first):
    assert not comparison(record(first),today=date(2026,6,3))["eligible"]


@pytest.mark.parametrize("calculated", ["2026-05-23T00:00:00+00:00","2026-05-24T00:00:00+00:00"])
def test_retrospective_forecast_not_scored(calculated):
    p=record(); snapshot=json.loads(p.dynamic_dtm_initial_snapshot)
    snapshot["calculated_at"]=calculated; p.dynamic_dtm_initial_snapshot=json.dumps(snapshot)
    assert not comparison(p)["eligible"]


def test_summary_denominator_excludes_unusable_records_and_uses_absolute_error():
    report=harvest_report([record(date(2026,5,18)),record(date(2026,5,24)),record(None)])
    assert report["summary"] == {"total":3,"eligible":2,"within_window":2,"mean_absolute_error_days":3.0}
    assert harvest_report([])["summary"]["mean_absolute_error_days"] is None


def test_harvest_before_window_has_negative_error():
    row=comparison(record(date(2026,5,17)))
    assert row["prediction_error_days"] == -4 and row["within_window"] is False
