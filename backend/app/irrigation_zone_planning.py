"""Irrigation zone planting invariants for GrowMaster.

Physical valve membership is persistent. A shared valve is a single planting
decision unit: crop, variety, and sowing/transplant date must match.
No hardware commands are issued by this module.
"""
from dataclasses import dataclass
from datetime import date
from typing import Iterable


@dataclass(frozen=True)
class ZonePlanting:
    bed_id: int
    crop_id: int
    variety_id: int
    sowing_date: date
    transplant_date: date | None = None


def validate_zone_plantings(
    member_bed_ids: Iterable[int],
    proposed: Iterable[ZonePlanting],
) -> None:
    """Reject incomplete or inconsistent shared-zone planting proposals."""
    members = list(member_bed_ids)
    plantings = list(proposed)
    if not members or len(members) != len(set(members)):
        raise ValueError("Namakalna cona mora imeti enolične gredice.")
    if len(plantings) != len(members) or {p.bed_id for p in plantings} != set(members):
        raise ValueError("Zasaditev mora vključevati vse gredice istega ventila.")
    signatures = {
        (p.crop_id, p.variety_id, p.sowing_date, p.transplant_date)
        for p in plantings
    }
    if len(signatures) != 1:
        raise ValueError(
            "Vse gredice istega ventila morajo imeti enako kulturo, "
            "sorto in datuma setve oziroma presajanja."
        )


def zone_crop_candidates(
    member_bed_ids: Iterable[int],
    eligible_crop_ids_by_bed: dict[int, set[int]],
) -> set[int]:
    """Only suggest crops eligible on every member bed (e.g. crop rotation)."""
    members = list(member_bed_ids)
    if not members:
        return set()
    if any(bed_id not in eligible_crop_ids_by_bed for bed_id in members):
        return set()
    return set.intersection(*(eligible_crop_ids_by_bed[bed_id] for bed_id in members))
