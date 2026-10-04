"""Explicit, per-plan historical suggestions, never automatic calibration."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from statistics import median

from app.dynamic_dtm import ENGINE_VERSION
from app.harvest_comparison import comparison
from app.maturity import season_for_date


def snapshot(raw):
    try:
        value = json.loads(raw or "null")
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def suggestion(plan, history, *, today=None):
    today = today or date.today()
    current = snapshot(plan.dynamic_dtm_explanation)
    correction = current.get("history_correction")
    correction = correction if isinstance(correction, dict) else None
    row = {"plan_id": plan.id, "bed": plan.bed.name, "crop": plan.crop.name,
           "variety": plan.variety.name, "sowing_date": plan.sowing_date,
           "can_apply": False, "can_reset": False, "applied": bool(correction),
           "reason": None, "evidence": [], "distinct_dates": 0,
           "correction_days": 0, "before_days": current.get("dynamic_dtm_days"),
           "after_days": None, "after_date": None}
    if row["applied"]:
        row["correction_days"] = correction.get("days", 0)
        row["evidence"] = correction.get("evidence", [])
        row["distinct_dates"] = correction.get("distinct_dates", 0)
        row["after_days"] = current.get("dynamic_dtm_days")
        row["before_days"] = correction.get("baseline", {}).get("dynamic_dtm_days")
        row["after_date"] = current.get("predicted_harvest_date")
        row["can_reset"] = plan.status == "planned" and plan.sowing_date > today
        row["reason"] = "Potrjeni popravek velja samo za ta načrt. Pred novim predlogom ga odstrani."
        return row
    reference = plan.transplant_date or plan.sowing_date
    kind = "transplant" if plan.transplant_date else "sowing"
    if plan.status != "planned" or plan.sowing_date <= today:
        row["reason"] = "Popravek je na voljo samo pred začetkom setve načrta."
        return row
    try:
        days = current["dynamic_dtm_days"]
        season = season_for_date(reference)
        if (type(days) is not int or days < 1 or current.get("method") != "seasonal_fallback"
                or current.get("engine_version") != ENGINE_VERSION
                or current.get("reference_date") != reference.isoformat()
                or current.get("reference_kind") != kind
                or current.get("season") != season
                or current.get("seasonal_dtm_days") != days
                or current.get("catalog_dtm_days") != plan.variety.days_to_harvest
                or getattr(plan.variety, f"days_{season}") != days):
            raise ValueError()
        predicted = date.fromisoformat(current["predicted_harvest_date"])
        start = date.fromisoformat(current["predicted_harvest_start"])
        end = date.fromisoformat(current["predicted_harvest_end"])
        if predicted != reference + timedelta(days=days) or not reference < start <= predicted <= end:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        row["reason"] = "Potrebna je veljavna, aktualna sezonska napoved brez GDD popravka."
        return row
    for planting in history:
        if (planting.farm_id != plan.farm_id or planting.variety_id != plan.variety_id
                or planting.status != "completed" or not planting.completed_on
                or planting.completed_on > today):
            continue
        initial = snapshot(planting.dynamic_dtm_initial_snapshot)
        latest = snapshot(planting.dynamic_dtm_explanation)
        result = comparison(planting, today=today)
        if (not result["eligible"] or initial.get("history_correction")
                or initial.get("method") != "seasonal_fallback"
                or initial.get("engine_version") != ENGINE_VERSION
                or initial.get("reference_kind") != kind
                or initial.get("season") != season
                or initial.get("seasonal_dtm_days") != days
                or initial.get("dynamic_dtm_days") != days
                or initial.get("catalog_dtm_days") != current["catalog_dtm_days"]
                or initial.get("reference_date") != latest.get("reference_date")
                or initial.get("reference_kind") != latest.get("reference_kind")):
            continue
        # Do not interpret a shifted sowing/transplant as a biological DTM error.
        source_reference = result["reference_date"]
        if (season_for_date(source_reference) != season
                or (kind == "sowing" and source_reference != planting.sowing_date)
                or (kind == "transplant" and source_reference < planting.sowing_date)
                or result["predicted_harvest_date"] != source_reference + timedelta(days=days)):
            continue
        row["evidence"].append({"planting_id": planting.id,
                                "reference_date": source_reference,
                                "first_harvest_date": result["first_harvest_date"],
                                "error_days": result["prediction_error_days"]})
    by_date = {}
    for evidence in row["evidence"]:
        by_date.setdefault(evidence["reference_date"], []).append(evidence["error_days"])
    errors = [median(values) for values in by_date.values()]
    row["distinct_dates"] = len(errors)
    if len(errors) < 3:
        row["reason"] = "Potrebni so vsaj trije različni referenčni datumi primerljivih zaključenih zasaditev."
        return row
    if max(errors) - min(errors) > max(4, math.floor(days * .2)):
        row["reason"] = "Odmiki se preveč razlikujejo; enoten popravek ni predlagan."
        return row
    middle = median(errors)
    limit = min(7, math.floor(days * .2))
    correction = max(-limit, min(limit, int(math.copysign(math.floor(abs(middle) + .5), middle))))
    if correction == 0:
        row["reason"] = "Zgodovina ne kaže dovolj velikega enotnega odmika za popravek."
        return row
    row.update(can_apply=True, correction_days=correction, after_days=days + correction,
               after_date=predicted + timedelta(days=correction),
               reason="Mediana odmikov po referenčnih datumih; omejeno na 20 % DTM in največ 7 dni. Zanesljivost ostane nizka.")
    return row


def learning_report(plans, history, *, today=None):
    today = today or date.today()
    rows = [suggestion(p, history, today=today) for p in plans]
    def values(record):
        return {c.name: getattr(record, c.name) for c in record.__table__.columns}
    payload = {"today": today, "rows": rows, "plans": [values(p) for p in plans],
               "varieties": [values(p.variety) for p in plans],
               "history": [[values(p), values(p.variety), [values(h) for h in sorted(p.harvests, key=lambda h: h.id)]] for p in history]}
    token = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return {"token": token, "rows": rows}


def save_result(plan, result):
    plan.dynamic_dtm_days = result["dynamic_dtm_days"]
    plan.dynamic_dtm_confidence = result["confidence"]
    plan.predicted_harvest_start = date.fromisoformat(result["predicted_harvest_start"])
    plan.predicted_harvest_end = date.fromisoformat(result["predicted_harvest_end"])
    plan.dynamic_dtm_explanation = json.dumps(result, ensure_ascii=False, default=str)


def apply_suggestion(plan, row):
    baseline = snapshot(plan.dynamic_dtm_explanation)
    result = dict(baseline)
    delta = timedelta(days=row["correction_days"])
    result["dynamic_dtm_days"] = row["after_days"]
    result["adjustment_days"] = row["after_days"] - baseline["catalog_dtm_days"]
    result["predicted_harvest_date"] = str(row["after_date"])
    # Keep the original interval too; a small sample never narrows uncertainty.
    start = date.fromisoformat(baseline["predicted_harvest_start"])
    end = date.fromisoformat(baseline["predicted_harvest_end"])
    reference = date.fromisoformat(baseline["reference_date"])
    result["predicted_harvest_start"] = str(max(reference + timedelta(days=1), min(start, start + delta)))
    result["predicted_harvest_end"] = str(max(end, end + delta))
    result["confidence"] = "low"
    result["history_correction"] = {"days": row["correction_days"], "evidence": row["evidence"],
        "distinct_dates": row["distinct_dates"], "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "policy_version": "1.24.37", "baseline": baseline}
    result["reasons"] = [*baseline["reasons"], f"Ročno potrjen zgodovinski popravek za ta načrt: {row['correction_days']:+d} dni. Interval ni zožen; ne gre za umerjen agronomski model."]
    save_result(plan, result)
