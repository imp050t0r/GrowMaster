"""Read-only evidence from original forecasts and recorded first harvests."""
from datetime import date, datetime
import json


def comparison(planting, *, today=None):
    today = today or date.today()
    harvests = [h for h in planting.harvests if h.farm_id == planting.farm_id]
    first = min((h.harvest_date for h in harvests), default=None)
    row = {
        "planting_id": planting.id, "crop": planting.crop.name,
        "variety": planting.variety.name, "bed": planting.bed.name,
        "sowing_date": planting.sowing_date, "status": planting.status,
        "completed_on": planting.completed_on, "first_harvest_date": first,
        "harvest_count": len(harvests),
        "planned_harvest_date": None, "predicted_harvest_date": None,
        "predicted_harvest_start": None, "predicted_harvest_end": None,
        "reference_date": None, "reference_kind": None,
        "days_from_initial_reference": None, "planned_error_days": None,
        "prediction_error_days": None, "within_window": None,
        "eligible": False, "reason": None,
    }
    try:
        snapshot = json.loads(planting.dynamic_dtm_initial_snapshot or "null")
        if not isinstance(snapshot, dict):
            raise ValueError()
        reference = date.fromisoformat(snapshot["reference_date"])
        predicted = date.fromisoformat(snapshot["predicted_harvest_date"])
        start = date.fromisoformat(snapshot["predicted_harvest_start"])
        end = date.fromisoformat(snapshot["predicted_harvest_end"])
        calculated = datetime.fromisoformat(snapshot["calculated_at"]).date()
        planned = date.fromisoformat(snapshot["planned_harvest_date"]) if snapshot.get("planned_harvest_date") else None
        kind = snapshot["reference_kind"]
        if kind not in ("sowing", "transplant") or not reference < start <= predicted <= end:
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        row["reason"] = "Manjka veljaven začetni posnetek napovedi; zgodovinske napovedi ne ustvarjamo za nazaj."
        return row
    row.update(planned_harvest_date=planned, predicted_harvest_date=predicted,
               predicted_harvest_start=start, predicted_harvest_end=end,
               reference_date=reference, reference_kind=kind)
    if first is None:
        row["reason"] = "Ni zabeleženega pobiranja. Zaključek kulture ni datum prve žetve."
    elif first > today or first < planting.sowing_date or first <= reference:
        row["reason"] = "Datum prvega pobiranja je v prihodnosti ali ni za datumom začetka rasti."
    elif calculated >= first:
        row["reason"] = "Začetna napoved je nastala na dan prvega pobiranja ali pozneje; izključena iz ocene točnosti."
    elif planting.completed_on and first > planting.completed_on:
        row["reason"] = "Prvo pobiranje je po zaključku kulture; preveri datume."
    else:
        row.update(eligible=True, days_from_initial_reference=(first-reference).days,
                   planned_error_days=(first-planned).days if planned else None,
                   prediction_error_days=(first-predicted).days,
                   within_window=start <= first <= end)
    return row


def harvest_report(plantings, *, today=None):
    rows = [comparison(p, today=today) for p in plantings]
    eligible = [r for r in rows if r["eligible"]]
    return {"rows": rows, "summary": {
        "total": len(rows), "eligible": len(eligible),
        "within_window": sum(r["within_window"] for r in eligible),
        "mean_absolute_error_days": round(sum(abs(r["prediction_error_days"]) for r in eligible)/len(eligible), 1) if eligible else None,
    }}
