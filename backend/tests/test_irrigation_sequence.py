import pytest

from app.irrigation_sequence import SequenceEvent, ValveRun, preview_sequence


def test_empty_plan_never_starts_pump():
    assert preview_sequence([]) == ()


def test_single_valve_waits_before_start_and_after_stop():
    assert preview_sequence([ValveRun(1, "opensprinkler-1", 0, 60)]) == (
        SequenceEvent(0, "valve_open", "opensprinkler-1", 0),
        SequenceEvent(5, "pump_on"),
        SequenceEvent(65, "pump_off"),
        SequenceEvent(70, "valve_close", "opensprinkler-1", 0),
    )


def test_cross_controller_transition_keeps_pump_running_and_overlaps_five_seconds():
    assert preview_sequence([
        ValveRun(1, "opensprinkler-1", 71, 10),
        ValveRun(2, "opensprinkler-2", 71, 20),
    ]) == (
        SequenceEvent(0, "valve_open", "opensprinkler-1", 71),
        SequenceEvent(5, "pump_on"),
        SequenceEvent(15, "valve_open", "opensprinkler-2", 71),
        SequenceEvent(20, "valve_close", "opensprinkler-1", 71),
        SequenceEvent(40, "pump_off"),
        SequenceEvent(45, "valve_close", "opensprinkler-2", 71),
    )


@pytest.mark.parametrize("field,value", [
    ("bed_id", 0), ("bed_id", True), ("bed_id", "1"),
    ("controller_id", "opensprinkler-3"), ("controller_id", ""),
    ("station_number", -1), ("station_number", 72),
    ("station_number", True), ("station_number", 1.0),
    ("run_seconds", 0), ("run_seconds", -1), ("run_seconds", 86401),
    ("run_seconds", True), ("run_seconds", 1.5),
    ("run_seconds", float("nan")), ("run_seconds", float("inf")),
])
def test_invalid_input_rejected_even_after_valid_run(field, value):
    values = dict(bed_id=2, controller_id="opensprinkler-2", station_number=1, run_seconds=60)
    values[field] = value
    with pytest.raises(ValueError):
        preview_sequence([ValveRun(1, "opensprinkler-1", 0, 60), ValveRun(**values)])


@pytest.mark.parametrize("second", [
    ValveRun(1, "opensprinkler-2", 0, 60),
    ValveRun(2, "opensprinkler-1", 0, 60),
])
def test_duplicate_bed_or_valve_rejected(second):
    with pytest.raises(ValueError):
        preview_sequence([ValveRun(1, "opensprinkler-1", 0, 60), second])


def test_full_capacity_never_runs_pump_without_open_valve_and_finishes_off():
    runs = [ValveRun(controller * 72 + station + 1, f"opensprinkler-{controller + 1}",
                     station, 1 if station % 2 else 86400)
            for controller in range(2) for station in range(72)]
    events = preview_sequence(iter(runs))
    opened = set()
    pump_on = False
    previous_time = -1
    for event in events:
        assert event.at_seconds > previous_time
        previous_time = event.at_seconds
        valve = (event.controller_id, event.station_number)
        if event.action == "valve_open":
            assert valve not in opened
            opened.add(valve)
        elif event.action == "valve_close":
            opened.remove(valve)
        elif event.action == "pump_on":
            assert not pump_on
            pump_on = True
        else:
            assert pump_on
            pump_on = False
        assert not pump_on or opened
        assert len(opened) <= 2
    assert not opened and not pump_on
    assert sum(e.action == "pump_on" for e in events) == 1
    assert sum(e.action == "pump_off" for e in events) == 1
    assert events[-1].at_seconds == sum(r.run_seconds for r in runs) + 5 * (len(runs) + 1)
