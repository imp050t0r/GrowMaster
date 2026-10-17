"""Conservative shared-valve screening, not a hydraulic or weather forecast."""
from datetime import date, timedelta
from math import isclose

from sqlalchemy import select

from app.irrigation_routes import BedProfile, CropProfile
from app.models import Bed, CropPlan, IrrigationBedProfile, IrrigationCropProfile, Planting
from app.succession import field_start, release_estimate


def load_context(db, farm_id):
    beds = {b.id: b for b in db.scalars(select(Bed).where(Bed.farm_id == farm_id))}
    profiles = {r.bed_id: BedProfile.model_validate_json(r.parameters) for r in db.scalars(
        select(IrrigationBedProfile).where(IrrigationBedProfile.farm_id == farm_id)) if r.bed_id in beds}
    crops = {r.crop_id: CropProfile.model_validate_json(r.parameters) for r in db.scalars(
        select(IrrigationCropProfile).where(IrrigationCropProfile.farm_id == farm_id))}
    return {"beds": beds, "profiles": profiles, "crops": crops}


def crop_cycle(record, *, today=None):
    end, _ = release_estimate(record, active=record.status == "active", today=today)
    return {"bed_id": record.bed_id, "crop_id": record.crop_id, "start": field_start(record),
            "target": record.predicted_harvest_start or record.expected_harvest_date, "end": end}


def proposal_cycle(row):
    return {"bed_id": row["bed_id"], "crop_id": row["crop_id"],
            "start": row["transplant_date"] or row["sowing_date"],
            "target": date.fromisoformat(row["predicted_harvest_start"]),
            "end": date.fromisoformat(row["predicted_harvest_end"])}


def _kc(cycle, profile, day):
    days = (cycle["target"] - cycle["start"]).days
    if days <= 0:
        return None
    progress = (day - cycle["start"]).days / days
    return profile.kc_initial if progress < .2 else profile.kc_mid if progress < .8 else profile.kc_late


def assess(cycle, others, context):
    """Require matching daily Kc and water-storage proxies throughout overlap.

    Exact matching is intentional: crop stress tolerances and distribution losses
    are unknown. Source measurement: 20 L / 15 s = 80 L/min at 2 bar; retain the
    project's conservative 75 L/min planning ceiling, not a commissioning approval.
    """
    profiles, beds, crops = context["profiles"], context["beds"], context["crops"]
    bp = profiles.get(cycle["bed_id"])
    station = bp.opensprinkler_station_entity if bp else None
    members = [bid for bid, p in profiles.items() if station and p.opensprinkler_station_entity == station]
    if len(members) < 2 and not (bp and bp.valve_mode == "shared"):
        return {"compatible": True, "shared": False, "reasons": []}
    reasons = []
    if not station or len(members) < 2:
        reasons.append("Skupni ventil nima popolne vezave vsaj dveh gredic.")
    if len({p.opensprinkler_station_entity for p in profiles.values() if p.opensprinkler_station_entity}) > 72:
        reasons.append("Presežena je omejitev 72 fizičnih con.")
    bed = beds[cycle["bed_id"]]
    total_flow = 0
    for bid in members:
        other, ob = profiles[bid], beds[bid]
        if other.valve_mode != "shared":
            reasons.append(f"Gredica {bid} mora biti označena kot del skupnega ventila.")
        if not (isclose(bed.width_m, ob.width_m, abs_tol=.001) and isclose(bed.length_m, ob.length_m, abs_tol=.001)):
            reasons.append(f"Gredica {bid} nima enakih mer.")
        if other.flow_l_min is None or bp.flow_l_min is None:
            reasons.append(f"Manjka pretok gredice {bid}; hidravlika ni preverljiva.")
        else:
            total_flow += other.flow_l_min
            if not isclose(other.flow_l_min, bp.flow_l_min, rel_tol=0, abs_tol=.001):
                reasons.append(f"Gredica {bid} nima enakega pretoka kapljičnih cevi.")
        if any(not isclose(getattr(other, key), getattr(bp, key), rel_tol=0, abs_tol=.001)
               for key in ("field_capacity_pct", "wilting_point_pct", "efficiency_pct")):
            reasons.append(f"Gredica {bid} nima primerljivih tal in učinkovitosti namakanja.")
    if total_flow > 75:
        reasons.append("Skupni pretok ventila presega podanih 75 L/min črpalke.")
    cp = crops.get(cycle["crop_id"])
    if cp is None:
        reasons.append("Manjka vodni profil izbrane kulture.")
    if cycle["end"] is None or cycle["target"] <= cycle["start"]:
        reasons.append("Manjka veljavna napoved razvoja ali sprostitve gredice.")
    configuration_valid = not reasons
    if configuration_valid:
        for other in others:
            if other["bed_id"] not in members or other["bed_id"] == cycle["bed_id"]:
                continue
            start = max(cycle["start"], other["start"])
            end = min(cycle["end"], other["end"] or date.max)
            if start > end:
                continue
            op = crops.get(other["crop_id"])
            if other["end"] is None or op is None or other["target"] <= other["start"]:
                reasons.append(f"Gredica {other['bed_id']} nima zanesljivega profila ali konca zasedenosti.")
                continue
            if not isclose(cp.root_depth_m * cp.depletion_fraction, op.root_depth_m * op.depletion_fraction,
                           rel_tol=0, abs_tol=.001):
                reasons.append(f"Gredica {other['bed_id']} zahteva drugačen prag vodnega primanjkljaja.")
                continue
            for offset in range((end-start).days + 1):
                day = start + timedelta(days=offset)
                if not isclose(_kc(cycle, cp, day), _kc(other, op, day), rel_tol=0, abs_tol=.001):
                    reasons.append(f"Gredica {other['bed_id']}: nezdružljiv Kc razvojnih faz na {day}.")
                    break
    return {"compatible": not reasons, "shared": True, "can_shift": configuration_valid, "station": station,
            "bed_ids": sorted(members), "estimated_zone_flow_l_min": total_flow,
            "hydraulic_status": "unverified_distribution", "reasons": reasons}


def validate_plan(db, plan, farm_id):
    context = load_context(db, farm_id)
    records = list(db.scalars(select(CropPlan).where(CropPlan.farm_id == farm_id, CropPlan.status == "planned")))
    records += list(db.scalars(select(Planting).where(Planting.farm_id == farm_id, Planting.status == "active")))
    return assess(crop_cycle(plan), [crop_cycle(r) for r in records if r is not plan], context)
