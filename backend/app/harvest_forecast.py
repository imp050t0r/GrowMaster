"""Read-only first-harvest schedule; quantities remain user-entered estimates."""
from datetime import date, timedelta
import json
import math


def _window(record, source_plan=None):
    reference_record = source_plan or record
    reference = getattr(reference_record, "transplant_date", None) or reference_record.sowing_date
    kind = "transplant" if getattr(reference_record, "transplant_date", None) else "sowing"
    try:
        prediction = json.loads(record.dynamic_dtm_explanation or "null")
        center = date.fromisoformat(prediction["predicted_harvest_date"])
        start, end = record.predicted_harvest_start, record.predicted_harvest_end
        if (prediction["reference_date"] != reference.isoformat()
                or prediction["reference_kind"] != kind
                or reference_record.sowing_date != record.sowing_date
                or not reference < start <= center <= end
                or prediction["predicted_harvest_start"] != start.isoformat()
                or prediction["predicted_harvest_end"] != end.isoformat()):
            raise ValueError()
        return start, center, end, "dynamic", record.dynamic_dtm_confidence or "unknown", None
    except (ValueError, TypeError, KeyError):
        planned = record.expected_harvest_date
        return planned, planned, planned, "planned_fallback", "unknown", "Manjka veljavno shranjeno okno DTM za trenutni termin; prikazan je načrtovani datum, ne novo izračunana napoved."


def _quantity(record):
    value = getattr(record, "expected_yield_kg", None)
    return float(value) if value is not None and math.isfinite(value) and value > 0 else None


def _repeated(variety):
    methods = set((variety.harvest_methods or "").split(","))
    return (bool(methods & {"cut_and_regrow", "outer_leaves", "green_fruit"})
            or (variety.max_regrowth_cuts or 0) > 1
            or (variety.harvest_duration_days or 0) > 1)


def harvest_forecast(plans, plantings, harvests, start, end, *, today=None):
    today = today or date.today()
    linked = {}
    for plan in plans:
        if plan.status == "activated" and plan.planting_id:
            linked.setdefault(plan.planting_id, []).append(plan)
    first_harvested = {h.planting_id for h in harvests if h.harvest_date <= today}
    sources = [(p, "plan", p) for p in plans if p.status == "planned"]
    for planting in plantings:
        if planting.status == "active" and planting.id not in first_harvested:
            matches = [p for p in linked.get(planting.id, [])
                       if (p.crop_id, p.variety_id, p.bed_id, p.sowing_date)
                       == (planting.crop_id, planting.variety_id, planting.bed_id, planting.sowing_date)]
            sources.append((planting, "planting", matches[0] if len(matches) == 1 else None))
    rows = []
    for record, source, source_plan in sources:
        window_start, center, window_end, basis, confidence, warning = _window(record, source_plan)
        if window_start > end or window_end < start:
            continue
        quantity = _quantity(source_plan) if source_plan is not None else None
        repeated = _repeated(record.variety)
        rows.append({
            "id": record.id, "source": source, "source_plan_id": source_plan.id if source_plan else None,
            "crop_id": record.crop_id, "crop": record.crop.name,
            "variety": record.variety.name, "bed": record.bed.name,
            "planned_harvest_date": record.expected_harvest_date,
            "window_start": window_start, "center_date": center, "window_end": window_end,
            "basis": basis, "confidence": confidence, "warning": warning,
            "overdue": window_end < today,
            "planned_cycle_kg": quantity,
            "scheduled_first_harvest_kg": quantity if not repeated else None,
            "quantity_reason": "Sorta podpira večkratno pobiranje; količine po pobiranjih niso določene." if repeated else (
                "Ni enoznačno povezane vnesene količine pridelka." if quantity is None else None),
        })
    rows.sort(key=lambda row: (row["center_date"], row["crop"], row["variety"], row["source"], row["id"]))
    actual = [h for h in harvests if start <= h.harvest_date <= min(end, today)
              and h.quality != "waste" and math.isfinite(h.quantity_kg) and h.quantity_kg > 0]
    weeks = []
    cursor = start
    while cursor <= end:
        week_end = min(end, cursor + timedelta(days=6-cursor.weekday()))
        scheduled = [r for r in rows if cursor <= r["center_date"] <= week_end]
        estimated = [r["scheduled_first_harvest_kg"] for r in scheduled
                     if r["scheduled_first_harvest_kg"] is not None]
        weeks.append({
            "start": cursor, "end": week_end,
            "scheduled_count": len(scheduled),
            "window_overlap_count": sum(r["window_start"] <= week_end and r["window_end"] >= cursor for r in rows),
            "scheduled_kg": round(sum(estimated), 2) if estimated else None,
            "unknown_quantity_count": len(scheduled)-len(estimated),
            "actual_kg": round(sum(h.quantity_kg for h in actual if cursor <= h.harvest_date <= week_end), 2),
            "rows": scheduled,
        })
        cursor = week_end + timedelta(days=1)
    return {"start": start, "end": end, "rows": rows, "weeks": weeks,
            "first_harvest_count": len(rows),
            "fallback_count": sum(r["basis"] == "planned_fallback" for r in rows),
            "overdue_count": sum(r["overdue"] for r in rows),
            "actual_kg": round(sum(h.quantity_kg for h in actual), 2)}
