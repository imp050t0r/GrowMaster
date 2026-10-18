"""Conservative shared-valve screening, not a hydraulic or weather forecast."""
from datetime import date, timedelta
from math import isclose
import hashlib
import json
from types import SimpleNamespace

from sqlalchemy import select

from app.irrigation_routes import BedProfile, CropProfile
from app.models import Bed, CropPlan, IrrigationBedProfile, IrrigationCropProfile, Planting
from app.succession import field_start, release_estimate
from app.dynamic_dtm import store_prediction
from app.dtm_learning import apply_suggestion, save_result, snapshot


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


def check_succession_irrigation(report, plans, plantings, context):
    """Screen proposed dates and destinations without changing stored records."""
    profiles = {kind: {key: value.model_dump(mode="json") for key, value in context[kind].items()}
                for kind in ("profiles", "crops")}
    report["token"] = hashlib.sha256((report["token"] + json.dumps(profiles, sort_keys=True)).encode()).hexdigest()
    records = [*plans, *(p for p in plantings if p.status == "active")]
    by_id = {p.id: p for p in plans}
    for group in report["beds"]:
        for row in group["plans"]:
            plan = by_id[row["plan_id"]]
            peers = [crop_cycle(p) for p in records if p is not plan]
            candidate = SimpleNamespace(**{c.name: getattr(plan, c.name) for c in plan.__table__.columns},
                                        variety=plan.variety)
            alternatives = []
            for bed in row["alternative_beds"]:
                candidate.bed_id = bed["id"]
                if assess(crop_cycle(candidate), peers, context)["compatible"]:
                    alternatives.append(bed)
            row["alternative_beds"] = alternatives
            candidate.bed_id = plan.bed_id
            if row["shift_days"]:
                for name, value in row["proposed"].items():
                    setattr(candidate, name, value)
                store_prediction(candidate, plan.variety)
                check = assess(crop_cycle(candidate), peers, context)
                row["irrigation_reasons"] = check["reasons"]
                if not check["compatible"]:
                    row["blocked"] = True
                    row["warnings"].extend(check["reasons"])
                    group["can_apply"] = False
    return report


def planning_conflicts(db, farm_id):
    """Report existing conflicts without hiding newly measured profile values."""
    context = load_context(db, farm_id)
    records = list(db.scalars(select(CropPlan).where(CropPlan.farm_id == farm_id, CropPlan.status == "planned")))
    records += list(db.scalars(select(Planting).where(Planting.farm_id == farm_id, Planting.status == "active")))
    cycles = [crop_cycle(record) for record in records]
    conflicts = []
    for index, record in enumerate(records):
        if record.bed_id not in context["beds"]:
            continue
        check = assess(cycles[index], cycles[:index] + cycles[index+1:], context)
        if not check["compatible"]:
            conflicts.append({"record_type": "plans" if isinstance(record, CropPlan) else "plantings",
                              "record_id": record.id, "bed_id": record.bed_id,
                              "bed": context["beds"][record.bed_id].name, "crop_id": record.crop_id,
                              "reasons": check["reasons"]})
    return conflicts


def check_dtm_irrigation(report, plans, plantings, context):
    profiles = {kind: {key: value.model_dump(mode="json") for key, value in context[kind].items()}
                for kind in ("profiles", "crops")}
    # The learning token already covers all plans; add active peers and water profiles.
    profiles["active"] = [{c.name: getattr(p, c.name) for c in p.__table__.columns} for p in plantings]
    profiles["beds"] = {bid: (b.width_m, b.length_m) for bid, b in context["beds"].items()}
    report["token"] = hashlib.sha256((report["token"] + json.dumps(profiles, sort_keys=True, default=str)).encode()).hexdigest()
    by_id = {p.id: p for p in plans}
    records = [*plans, *plantings]
    for row in report["rows"]:
        plan = by_id[row["plan_id"]]
        for action in ("apply", "reset"):
            if not row["can_" + action]:
                continue
            candidate = SimpleNamespace(**{c.name: getattr(plan, c.name) for c in plan.__table__.columns},
                                        variety=plan.variety)
            if action == "apply":
                apply_suggestion(candidate, row)
            else:
                save_result(candidate, snapshot(plan.dynamic_dtm_explanation)["history_correction"]["baseline"])
            check = assess(crop_cycle(candidate), [crop_cycle(p) for p in records if p is not plan], context)
            if not check["compatible"]:
                row["can_" + action] = False
                row.setdefault("irrigation_reasons", {})[action] = check["reasons"]
    return report
