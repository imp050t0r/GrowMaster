from datetime import date

import pytest

from app.irrigation_zone_planning import (
    ZonePlanting,
    validate_zone_plantings,
    zone_crop_candidates,
)


def test_shared_valve_requires_identical_planting():
    rows = [ZonePlanting(1, 10, 20, date(2027, 3, 15)),
            ZonePlanting(2, 10, 20, date(2027, 3, 15))]
    validate_zone_plantings([1, 2], rows)


def test_rejects_different_variety():
    rows = [ZonePlanting(1, 10, 20, date(2027, 3, 15)),
            ZonePlanting(2, 10, 21, date(2027, 3, 15))]
    with pytest.raises(ValueError):
        validate_zone_plantings([1, 2], rows)


def test_rejects_missing_bed():
    with pytest.raises(ValueError):
        validate_zone_plantings([1, 2], [ZonePlanting(1, 10, 20, date(2027, 3, 15))])


def test_rotation_candidates_must_work_for_every_bed():
    assert zone_crop_candidates([1, 2], {1: {10, 11}, 2: {11, 12}}) == {11}


def test_rejects_different_sowing_date():
    rows = [ZonePlanting(1, 10, 20, date(2027, 3, 15)),
            ZonePlanting(2, 10, 20, date(2027, 3, 16))]
    with pytest.raises(ValueError):
        validate_zone_plantings([1, 2], rows)


def test_rejects_different_transplant_date():
    rows = [ZonePlanting(1, 10, 20, date(2027, 3, 15), date(2027, 4, 1)),
            ZonePlanting(2, 10, 20, date(2027, 3, 15), date(2027, 4, 2))]
    with pytest.raises(ValueError):
        validate_zone_plantings([1, 2], rows)


def test_rejects_duplicate_member_ids():
    with pytest.raises(ValueError):
        validate_zone_plantings(
            [1, 1],
            [ZonePlanting(1, 10, 20, date(2027, 3, 15))] * 2,
        )


def test_rejects_missing_rotation_eligibility():
    assert zone_crop_candidates([1, 2], {1: {10, 11}}) == set()
