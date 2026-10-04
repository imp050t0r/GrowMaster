"""Explainable local production proposals; never writes plans or invents yield."""
from datetime import date, timedelta

from app.dynamic_dtm import predict
from app.planting_advisor import ROTATION_RULES, rotation_families, score_candidate, seasonal_assessment
from app.succession import field_start, release_estimate


def _candidate(bed, crop, variety, plans, history, start, end, today):
    methods = set((variety.cultivation_methods or variety.planting_method or "").split(","))
    method = variety.planting_method if variety.planting_method in methods else (
        "direct" if "direct" in methods else "transplant" if "transplant" in methods else None)
    if method is None:
        return None
    nursery = variety.nursery_days if method == "transplant" else 0
    if nursery is None or nursery < 0 or nursery > (end-start).days:
        return None
    harvest_methods = set((variety.harvest_methods or "").split(","))
    if (harvest_methods & {"cut_and_regrow", "outer_leaves", "green_fruit"}
            or (variety.max_regrowth_cuts or 0) > 1 or (variety.harvest_duration_days or 0) > 1):
        # First harvest cannot establish the release of a repeated-harvest crop.
        return None
    field_date = start + timedelta(days=nursery)
    ordered = sorted(plans, key=lambda p: (field_start(p), p.id))
    for plan in ordered:
        occupied_end, _ = release_estimate(plan)
        occupied_end = occupied_end if occupied_end and occupied_end >= field_start(plan) else date.max
        prediction = predict(variety, field_date, reference_kind="transplant" if method == "transplant" else "sowing")
        candidate_end = date.fromisoformat(prediction["predicted_harvest_end"])
        if field_date <= occupied_end and candidate_end >= field_start(plan):
            if occupied_end == date.max:
                return None
            field_date = occupied_end + timedelta(days=1)
    if field_date > end:
        return None
    prediction = predict(variety, field_date, reference_kind="transplant" if method == "transplant" else "sowing")
    candidate_end = date.fromisoformat(prediction["predicted_harvest_end"])
    if candidate_end > end:
        return None
    families = rotation_families(crop.name, crop.family, variety.name)
    preceding = [(p.sowing_date, p.id, rotation_families(p.crop.name, p.crop.family, p.variety.name))
                 for p in history if p.sowing_date <= today]
    preceding.extend((field_start(p), p.id, rotation_families(p.crop.name, p.crop.family, p.variety.name))
                     for p in ordered if field_start(p) < field_date)
    preceding.sort(reverse=True, key=lambda p: (p[0], p[1]))
    recent = [p[2] for p in preceding[:int(ROTATION_RULES.get("history_cycles", 4))]]
    if not recent and bed.last_crop_family:
        recent = [{bed.last_crop_family}]
    following = [rotation_families(p.crop.name, p.crop.family, p.variety.name)
                 for p in ordered if field_start(p) > candidate_end]
    if any(families & previous for previous in recent + following):
        return None
    seasonal_score, seasonal_reason, warning = seasonal_assessment(crop.name, crop.category, field_date-timedelta(days=nursery))
    if seasonal_score <= -60:
        return None
    result = score_candidate(families, recent, prediction["dynamic_dtm_days"], seasonal_score, False, None)
    result["reasons"].insert(0, seasonal_reason)
    result["reasons"].append("Celotno ocenjeno okno prve žetve se prilega obdobju brez prekrivanja z obstoječimi načrti.")
    if warning:
        result["warnings"].append(warning)
    if not recent:
        result["warnings"].append("Ni zgodovine kolobarja; pred shranjevanjem preveri pretekle kulture.")
    result["warnings"].append("DTM uporablja sezonsko oceno; vreme in učenje iz zgodovine nista samodejno uporabljena.")
    return {"bed_id": bed.id, "bed": bed.name, "crop_id": crop.id, "crop": crop.name,
            "variety_id": variety.id, "variety": variety.name,
            "sowing_date": field_date-timedelta(days=nursery),
            "transplant_date": field_date if method == "transplant" else None,
            "expected_harvest_date": prediction["predicted_harvest_date"],
            "predicted_harvest_start": prediction["predicted_harvest_start"],
            "predicted_harvest_end": prediction["predicted_harvest_end"],
            "dynamic_dtm_days": prediction["dynamic_dtm_days"], "confidence": prediction["confidence"],
            "expected_yield_kg": None, **result}


def production_proposals(beds, crops, plans, plantings, start, end, max_beds, *, today=None):
    today = today or date.today()
    active_beds = {p.bed_id for p in plantings if p.status == "active"}
    proposals, skipped, counts = [], [], {}
    for bed in sorted(beds, key=lambda b: b.id):
        if len(proposals) >= max_beds:
            break
        if bed.status != "empty" or bed.id in active_beds:
            skipped.append({"bed_id": bed.id, "bed": bed.name, "reason": "Gredica ni potrjeno prosta; aktivne zasaditve niso samodejno zaključene."})
            continue
        bed_plans = [p for p in plans if p.bed_id == bed.id and p.status == "planned"]
        history = [p for p in plantings if p.bed_id == bed.id and p.status == "completed"
                   and (not p.completed_on or p.completed_on <= today)]
        candidates = []
        for crop in crops:
            for variety in sorted(crop.varieties, key=lambda v: v.id):
                try:
                    candidate = _candidate(bed, crop, variety, bed_plans, history, start, end, today)
                except (OverflowError, TypeError, ValueError):
                    candidate = None
                if candidate:
                    candidates.append(candidate)
        if not candidates:
            skipped.append({"bed_id": bed.id, "bed": bed.name, "reason": "Ni ustrezne kombinacije: preveri kolobar, prosto obdobje, sezono, način vzgoje in podatke sorte. Večkratno pobiranje ni samodejno razporejeno."})
            continue
        candidates.sort(key=lambda c: (counts.get(c["crop_id"], 0), -c["score"], c["sowing_date"], c["crop_id"], c["variety_id"]))
        chosen = candidates[0]
        proposals.append(chosen)
        counts[chosen["crop_id"]] = counts.get(chosen["crop_id"], 0)+1
    return {"start": start, "end": end, "as_of": today, "method": "local_rules",
            "proposals": proposals, "skipped_beds": skipped,
            "unassigned_crops": [{"crop_id": c.id, "crop": c.name} for c in crops if c.id not in counts],
            "note": "Začetni lokalni predlog po pravilih: največ ena nova kultura na gredico, izbrane kulture so razporejene čim bolj enakomerno. Ni globalna optimizacija, napoved količin ali zagotovilo dovolj časa in semena. Prenos v obrazec še ne shrani načrta."}
