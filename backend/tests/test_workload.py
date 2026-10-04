from datetime import date, datetime, timedelta
from types import SimpleNamespace as NS

from app.workload import workload_report

START=date(2027,3,1)
END=date(2027,3,14)


def task(id,day=START,minutes=None,status="planned",kind="irrigation",width=.8):
    return NS(id=id,status=status,task_type=kind,due_date=day,
              duration_minutes=minutes,completed_at=datetime.combine(day,datetime.min.time()) if status=="completed" else None,
              bed=NS(width_m=width,length_m=15))


def event(day=START,kind="task",task_id=1):
    return dict(date=day,type=kind,title="Test activity",task_id=task_id)


def test_empty_report_has_empty_weeks_and_unknown_hours():
    report=workload_report([],[],[],START,END)
    assert len(report['weeks'])==2 and report['activity_count']==0
    assert all(w['estimated_hours'] is None for w in report['weeks'])


def test_boundaries_and_partial_week_use_calendar_dates():
    start=START+timedelta(days=2); end=START+timedelta(days=8)
    events=[event(day=start),event(day=START+timedelta(days=6),kind='sowing'),event(day=end,kind='delivery'),event(day=end+timedelta(days=1))]
    report=workload_report(events,[],[],start,end)
    assert [w['activity_count'] for w in report['weeks']]==[2,1]
    assert report['weeks'][0]['end']==date(2027,3,7)
    assert report['weeks'][1]['counts']['delivery']==1
    assert report['peak_week_activity_count']==2


def test_estimate_requires_three_completion_dates_and_remains_partial():
    history=[task(i,day=START-timedelta(days=i),minutes=30+i*10,status='completed') for i in (1,2,3)]
    report=workload_report([event(),event(kind='sowing',task_id=None)],[task(1)],history,START,END,today=START)
    week=report['weeks'][0]
    assert week['estimated_hours']==.83 and week['estimated_activity_count']==1
    assert week['unknown_activity_count']==1 and week['activities'][0]['estimated_minutes'] is None
    assert week['activities'][1]['estimated_minutes']==50
    assert workload_report([event()],[task(1)],history[:2],START,END,today=START)['weeks'][0]['estimated_hours'] is None


def test_repeated_same_day_tasks_have_one_date_weight():
    history=[task(i,day=START-timedelta(days=1),minutes=100,status='completed') for i in range(1,8)]
    history += [task(20,day=START-timedelta(days=2),minutes=20,status='completed'),task(21,day=START-timedelta(days=3),minutes=30,status='completed')]
    report=workload_report([event()],[task(1)],history,START,END,today=START)
    assert report['weeks'][0]['activities'][0]['estimated_minutes']==30
    assert workload_report([event()],[task(1)],history[:7],START,END,today=START)['weeks'][0]['estimated_hours'] is None


def test_different_bed_sizes_types_future_and_invalid_durations_are_excluded():
    history=[task(i,day=START-timedelta(days=i),minutes=30,status='completed') for i in (1,2,3)]
    history[0].bed.width_m=1
    history[1].task_type='growth_check'
    history[2].completed_at=datetime(2027,3,2)
    history += [task(4,day=START-timedelta(days=4),minutes=-10,status='completed')]
    assert workload_report([event()],[task(1)],history,START,END,today=START)['weeks'][0]['estimated_hours'] is None


def test_no_task_estimate_is_invented_from_pending_duration():
    pending=task(1,minutes=200)
    assert workload_report([event()],[pending],[],START,END)['weeks'][0]['unknown_activity_count']==1
