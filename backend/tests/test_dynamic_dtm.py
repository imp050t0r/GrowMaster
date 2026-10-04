from datetime import date, timedelta
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from app.dynamic_dtm import ClimateInput, DTM_COLUMNS, predict, store_prediction
from app.migrations import add_dynamic_dtm


def variety(**values):
    return SimpleNamespace(days_to_harvest=30, days_spring=30, days_summer=27,
                           days_autumn=35, days_winter=44, **values)


def climate(temperatures, **kwargs):
    return ClimateInput(source="Test station", calibration_source="Test-only calibration",
                        base_temperature_c=5, target_gdd=100,
                        temperatures=temperatures, **kwargs)


def series(mean, count=30, start=date(2026, 5, 1), kind="observed"):
    return [{"day": start + timedelta(days=i), "mean_c": mean, "kind": kind} for i in range(count)]


def test_fallback_preserves_catalog_and_seasonal_values():
    plant = variety()
    result = predict(plant, date(2026, 7, 1))
    assert plant.days_to_harvest == 30
    assert result["dynamic_dtm_days"] == 27
    assert result["confidence"] == "low"
    assert result["fallback"] is True
    assert result["predicted_harvest_start"] < result["predicted_harvest_date"] < result["predicted_harvest_end"]


def test_gdd_warm_and_cold_series_do_not_double_apply_seasonality():
    warm = predict(variety(), date(2026, 5, 1), climate(series(15)))
    cold = predict(variety(), date(2026, 5, 1), climate(series(10)))
    assert warm["dynamic_dtm_days"] == 10
    assert cold["dynamic_dtm_days"] == 20
    assert warm["method"] == "gdd"
    assert warm["confidence"] == "medium"


@pytest.mark.parametrize("rows", [series(4), series(15, 5), series(15)[1:], series(15)[:4] + series(15)[5:]])
def test_missing_or_insufficient_heat_falls_back(rows):
    result = predict(variety(), date(2026, 5, 1), climate(rows))
    assert result["dynamic_dtm_days"] == 30
    assert result["fallback"] is True


def test_uncalibrated_temperature_cannot_change_dtm():
    result = predict(variety(), date(2026, 5, 1), ClimateInput(temperatures=series(40)))
    assert result["dynamic_dtm_days"] == 30
    assert result["gdd_accumulated"] is None


def test_forecast_is_not_high_confidence():
    result = predict(variety(), date(2026, 5, 1), climate(series(15, kind="forecast")))
    assert result["method"] == "gdd"
    assert result["confidence"] == "low"


def test_invalid_temperatures_are_rejected():
    for rows in [series(float("nan")), series(100), series(15) + series(15)]:
        with pytest.raises(ValidationError):
            climate(rows)
    with pytest.raises(ValidationError):
        climate(series(15, start=date.today() + timedelta(days=1)))


def test_snapshot_uses_transplant_reference_and_keeps_original_plan():
    record = SimpleNamespace(sowing_date=date(2026, 4, 1), transplant_date=date(2026, 5, 1),
                             expected_harvest_date=date(2026, 6, 7), dynamic_dtm_initial_snapshot=None)
    store_prediction(record, variety())
    original = record.dynamic_dtm_initial_snapshot
    store_prediction(record, variety(), climate(series(15)))
    assert record.expected_harvest_date == date(2026, 6, 7)
    assert record.dynamic_dtm_initial_snapshot == original
    assert json.loads(original)["reference_kind"] == "transplant"
    assert json.loads(original)["planned_harvest_date"] == "2026-06-07"
    assert record.dynamic_dtm_days == 10


def test_leap_year_and_year_boundary():
    plant = variety()
    plant.days_winter = 1
    assert predict(plant, date(2024, 2, 28))["predicted_harvest_date"] == "2024-02-29"
    assert predict(plant, date(2026, 12, 31))["predicted_harvest_date"] == "2027-01-01"


def test_additive_migration_is_repeatable_and_keeps_historical_dates():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for table in ("plantings", "crop_plans"):
            connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, expected_harvest_date DATE)"))
            connection.execute(text(f"INSERT INTO {table} VALUES (1, '2026-06-07')"))
        add_dynamic_dtm(connection)
        add_dynamic_dtm(connection)
        for table in ("plantings", "crop_plans"):
            assert set(DTM_COLUMNS) <= {c["name"] for c in inspect(connection).get_columns(table)}
            row = connection.execute(text(f"SELECT * FROM {table}")).mappings().one()
            assert row["expected_harvest_date"] == "2026-06-07"
            assert all(row[name] is None for name in DTM_COLUMNS)
