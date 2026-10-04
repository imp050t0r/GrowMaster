"""Read-only succession proposals. First harvest is not necessarily bed release."""
from datetime import date, timedelta
import hashlib
import json

from app.dynamic_dtm import predict
from app.planting_advisor import ROTATION_RULES, rotation_families, seasonal_assessment


def field_start(record):
    return getattr(record, "transplant_date", None) or record.sowing_date


def release_estimate(record, *, shift=0, active=False, today=None):
    today = today or date.today()
    offset = timedelta(days=shift)
    explicit = record.expected_bed_release_date
    if explicit:
        end, basis = explicit + offset, "manual"
    else:
        variety = record.variety
        methods = set((variety.harvest_methods or "").split(","))
        repeated = ((variety.harvest_duration_days or 0) > 1
                    or (variety.max_regrowth_cuts or 0) > 1
                    or bool(methods & {"cut_and_regrow", "outer_leaves", "green_fruit"}))
        if repeated:
            return None, "needs_release_date"
        predicted_end = record.predicted_harvest_end
        if shift:
            predicted_end = date.fromisoformat(predict(
                variety, field_start(record) + offset)["predicted_harvest_end"])
        end = max(record.expected_harvest_date + offset,
                  predicted_end or record.expected_harvest_date + offset)
        basis = "dynamic_window" if predicted_end else "planned_harvest"
    if active and end < today:
        return None, "active_overdue"
    return end, basis


def state_token(beds, plans, plantings, today):
    def values(record):
        return {column.name: getattr(record, column.name) for column in record.__table__.columns}
    varieties = {r.variety.id: r.variety for r in [*plans, *plantings]}
    crops = {r.crop.id: r.crop for r in [*plans, *plantings]}
    payload = {"today": today, "beds": [values(x) for x in beds],
               "plans": [values(x) for x in plans], "plantings": [values(x) for x in plantings],
               "varieties": [values(varieties[k]) for k in sorted(varieties)],
               "crops": [values(crops[k]) for k in sorted(crops)]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def label(record):
    return f"{record.crop.name} · {record.variety.name}"


def dates(record, shift=0):
    offset = timedelta(days=shift)
    return {"sowing_date": record.sowing_date + offset,
            "transplant_date": record.transplant_date + offset if record.transplant_date else None,
            "expected_harvest_date": record.expected_harvest_date + offset,
            "expected_bed_release_date": record.expected_bed_release_date + offset if record.expected_bed_release_date else None}


def alternatives(plan, beds, plans, plantings, today):
    if plan.sowing_date <= today:
        return []
    occupied = {p.bed_id for p in plans} | {p.bed_id for p in plantings if p.status == "active"}
    families = rotation_families(plan.crop.name, plan.crop.family, plan.variety.name)
    results = []
    for bed in beds:
        # Only entirely empty/unplanned beds of the same dimensions: no hidden
        # change to seed quantity, layout or expected yield when relocating.
        if bed.id == plan.bed_id or bed.id in occupied or bed.status != "empty":
            continue
        if abs(bed.width_m - plan.bed.width_m) > .001 or abs(bed.length_m - plan.bed.length_m) > .001:
            continue
        history = sorted((p for p in plantings if p.bed_id == bed.id and p.status == "completed"),
                         key=lambda p: (p.sowing_date, p.id), reverse=True)[:int(ROTATION_RULES.get("history_cycles", 4))]
        prior = set().union(*(rotation_families(p.crop.name, p.crop.family, p.variety.name) for p in history))
        if bed.last_crop_family:
            prior.add(bed.last_crop_family)
        if not families & prior:
            results.append({"id": bed.id, "name": bed.name})
    return results


def review(beds, plans, plantings, *, today=None):
    today = today or date.today()
    groups = []
    for bed in beds:
        active = [p for p in plantings if p.bed_id == bed.id and p.status == "active"]
        sequence = sorted((p for p in plans if p.bed_id == bed.id), key=lambda p: (field_start(p), p.id))
        if not active and not sequence:
            continue
        sources = []
        for current in active:
            end, basis = release_estimate(current, active=True, today=today)
            sources.append({"id": current.id, "record_type": "plantings", "label": label(current),
                            "expected_bed_release_date": current.expected_bed_release_date,
                            "occupied_through": end, "basis": basis,
                            "minimum_release_date": max(today, current.expected_harvest_date)})
        rows = []
        prior_end = None
        prior_unknown = False
        predecessor = None
        for plan in sequence:
            original_start = field_start(plan)
            candidate = max(original_start, prior_end + timedelta(days=1)) if prior_end else original_start
            unknown = prior_unknown
            blockers = [predecessor] if predecessor and (prior_unknown or candidate > original_start) else []
            # Active cycles are fixed. A future-dated active cycle may also
            # block a shifted proposal, so re-evaluate until the slot is clear.
            for _ in range(len(active) + 1):
                changed = False
                proposed_end, _ = release_estimate(plan, shift=(candidate - original_start).days, today=today)
                for current in active:
                    end, _ = release_estimate(current, active=True, today=today)
                    if proposed_end is not None and field_start(current) > proposed_end:
                        continue
                    if end is None:
                        unknown = True
                        if label(current) not in blockers:
                            blockers.append(label(current))
                    elif end >= candidate:
                        candidate = end + timedelta(days=1)
                        changed = True
                        if label(current) not in blockers:
                            blockers.append(label(current))
                if not changed:
                    break
            delta = (candidate - original_start).days
            end, basis = release_estimate(plan, shift=delta, today=today)
            warnings = []
            if unknown:
                warnings.append("Datum sprostitve predhodne kulture ni znan. Vpiši zadnji dan zasedenosti ali zaključi dejansko končan cikel.")
            if delta and plan.sowing_date <= today:
                warnings.append("Setev je danes ali v preteklosti; samodejni premik ni na voljo. Preveri dejansko stanje sadik.")
            if delta:
                _, reason, warning = seasonal_assessment(plan.crop.name, plan.crop.category, candidate)
                warnings.append(warning or reason)
            if basis == "needs_release_date":
                warnings.append("Sorta omogoča večkratno pobiranje. Za naslednjo sukcesijo vpiši zadnji dan zasedenosti grede.")
            rows.append({"plan_id": plan.id, "label": label(plan), "field_start": original_start,
                         "nursery_days": (plan.transplant_date - plan.sowing_date).days if plan.transplant_date else 0,
                         "shift_days": delta, "blocked": unknown,
                         "original": dates(plan), "proposed": dates(plan, delta),
                         "occupied_through": end, "basis": basis, "predecessors": blockers,
                         "warnings": warnings,
                         "minimum_release_date": plan.expected_harvest_date,
                         "alternative_beds": alternatives(plan, beds, plans, plantings, today) if delta or unknown else []})
            prior_end = end
            prior_unknown = unknown or end is None
            predecessor = label(plan)
        changes = [row for row in rows if row["shift_days"]]
        can_apply = bool(changes) and not any(row["blocked"] for row in rows) and all(
            row["original"]["sowing_date"] > today for row in changes)
        groups.append({"bed_id": bed.id, "bed": bed.name, "active": sources, "plans": rows,
                       "can_apply": can_apply, "change_count": len(changes)})
    return {"token": state_token(beds, plans, plantings, today), "as_of": today,
            "beds": groups, "turnover_days": 1,
            "note": "Predlog uporablja zadnji dan zasedenosti in naslednji dan za novo kulturo. Dynamic DTM je ocena prve žetve; večkratno pobiranje zahteva datum zaključka. Datumi se spremenijo šele z izbiro predloga."}
