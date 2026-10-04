"""Weekly planned activity counts with explicitly partial historical hours."""
from datetime import date, timedelta
from statistics import median


def task_key(task):
    bed = task.bed
    return (task.task_type, round(bed.width_m, 3), round(bed.length_m, 3)) if bed else (task.task_type, None, None)


def workload_report(events, pending_tasks, completed_tasks, start, end, *, today=None):
    today = today or date.today()
    history = {}
    for task in completed_tasks:
        if (task.status != "completed" or not task.completed_at
                or task.completed_at.date() > today or not task.duration_minutes
                or task.duration_minutes <= 0):
            continue
        history.setdefault(task_key(task), {}).setdefault(task.completed_at.date(), []).append(task.duration_minutes)
    estimates={}
    for key, days in history.items():
        if len(days)>=3:
            estimates[key]=(round(median(median(values) for values in days.values()),1),sum(len(values) for values in days.values()))
    pending = {t.id:t for t in pending_tasks if t.status == "planned"}
    rows=[]
    for event in events:
        if not start <= event["date"] <= end:
            continue
        row={**event,"estimated_minutes":None,"history_samples":0}
        task=pending.get(event.get("task_id"))
        if task:
            estimate=estimates.get(task_key(task))
            if estimate:
                # Each completion date has equal weight, despite multiple beds.
                row["estimated_minutes"],row["history_samples"]=estimate
        rows.append(row)
    rows.sort(key=lambda r:(r["date"],r["type"],r["title"]))
    weeks=[]; cursor=start
    while cursor<=end:
        week_end=min(end,cursor+timedelta(days=6-cursor.weekday()))
        activities=[r for r in rows if cursor<=r["date"]<=week_end]
        counts={kind:sum(r["type"]==kind for r in activities) for kind in ("sowing","transplant","planned_harvest","task","delivery")}
        estimates=[r["estimated_minutes"] for r in activities if r["estimated_minutes"] is not None]
        weeks.append({"start":cursor,"end":week_end,"activity_count":len(activities),"counts":counts,
                      "estimated_hours":round(sum(estimates)/60,2) if estimates else None,
                      "estimated_activity_count":len(estimates),"unknown_activity_count":len(activities)-len(estimates),
                      "activities":activities})
        cursor=week_end+timedelta(days=1)
    return {"start":start,"end":end,"weeks":weeks,"activity_count":len(rows),
            "peak_week_activity_count":max((w["activity_count"] for w in weeks),default=0)}
