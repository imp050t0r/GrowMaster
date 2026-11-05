import pytest

from app.irrigation_sequence import SequenceEvent, ValveRun, preview_sequence, simulate_sequence_fault


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


FAULT_RUNS = [ValveRun(1, "opensprinkler-1", 0, 10), ValveRun(2, "opensprinkler-2", 71, 20)]


def test_unconfirmed_first_valve_never_starts_pump_or_assumes_closed():
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="valve_open_unconfirmed", fault_at_seconds=0)
    assert result.events == (SequenceEvent(0, "pump_off"),)
    assert result.uncertain_event == SequenceEvent(0, "valve_open", "opensprinkler-1", 0)
    assert result.unresolved_valves == (("opensprinkler-1", 0),)
    assert result.status == "pump_stop_unconfirmed"
    assert result.pump_stop_confirmed_at_seconds is None
    assert result.simulation_only and result.manual_reset_required


def test_unconfirmed_transition_preserves_old_and_possibly_open_new_valve():
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="valve_open_unconfirmed", fault_at_seconds=15)
    assert result.events == (SequenceEvent(0, "valve_open", "opensprinkler-1", 0),
                             SequenceEvent(5, "pump_on"), SequenceEvent(15, "pump_off"))
    assert result.unresolved_valves == (("opensprinkler-1", 0), ("opensprinkler-2", 71))
    assert result.status == "pump_stop_unconfirmed"


def test_shutdown_waits_from_stop_confirmation_not_request():
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="valve_open_unconfirmed", fault_at_seconds=15,
        pump_stop_confirmed_after_seconds=7, valve_link_available=True, valve_close_confirmed=True)
    assert result.pump_stop_confirmed_at_seconds == 22
    assert result.events[-2:] == (SequenceEvent(27, "valve_close", "opensprinkler-1", 0),
                                  SequenceEvent(27, "valve_close", "opensprinkler-2", 71))
    assert result.status == "stopped" and result.unresolved_valves == ()
    assert result.manual_reset_required  # Even a successful abort never resumes watering.
    assert not any(e.action in {"pump_on", "valve_open"} for e in result.events if e.at_seconds >= 15)


@pytest.mark.parametrize("fault_time", [0, 1, 4, 5, 6, 14, 15, 16, 19, 20, 21, 39, 40, 41, 44, 45])
def test_connection_loss_at_or_between_commands_cannot_close_without_stop_confirmation(fault_time):
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="connection_lost", fault_at_seconds=fault_time,
                                     valve_link_available=True)
    after_fault = [e for e in result.events if e.at_seconds >= fault_time]
    assert after_fault == [SequenceEvent(fault_time, "pump_off")]
    assert result.status == "pump_stop_unconfirmed"
    assert result.unresolved_valves
    assert result.manual_reset_required


def test_lost_valve_connection_does_not_block_local_stop_or_claim_valves_closed():
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="connection_lost", fault_at_seconds=17,
                                     pump_stop_confirmed_after_seconds=2)
    assert result.pump_stop_confirmed_at_seconds == 19
    assert result.status == "valves_unconfirmed"
    assert result.unresolved_valves == (("opensprinkler-1", 0), ("opensprinkler-2", 71))
    assert not any(e.action == "valve_close" for e in result.events)


def test_issued_close_commands_are_not_close_confirmations():
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="connection_lost", fault_at_seconds=21,
        pump_stop_confirmed_after_seconds=0, valve_link_available=True)
    assert result.events[-1] == SequenceEvent(26, "valve_close", "opensprinkler-2", 71)
    assert result.unresolved_valves == (("opensprinkler-2", 71),)
    assert result.status == "valves_unconfirmed"


def test_uncertain_pump_start_is_followed_only_by_stop_request():
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="connection_lost", fault_at_seconds=5)
    assert result.uncertain_event == SequenceEvent(5, "pump_on")
    assert result.events[-1] == SequenceEvent(5, "pump_off")
    assert not any(e.action == "pump_on" for e in result.events)


def test_connection_loss_at_final_close_keeps_valve_unresolved():
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="connection_lost", fault_at_seconds=45)
    assert result.uncertain_event.action == "valve_close"
    assert result.unresolved_valves == (("opensprinkler-2", 71),)
    assert result.events[-1] == SequenceEvent(45, "pump_off")


@pytest.mark.parametrize("changes", [
    {"fault_kind":"unknown"}, {"fault_at_seconds":-1}, {"fault_at_seconds":46},
    {"fault_at_seconds":True}, {"fault_at_seconds":1.5},
    {"fault_kind":"valve_open_unconfirmed","fault_at_seconds":5},
    {"fault_kind":"valve_open_unconfirmed","fault_at_seconds":16},
    {"pump_stop_confirmed_after_seconds":-1}, {"pump_stop_confirmed_after_seconds":True},
    {"pump_stop_confirmed_after_seconds":float("inf")},
    {"valve_link_available":"true"}, {"valve_close_confirmed":1},
    {"valve_close_confirmed":True},
    {"valve_close_confirmed":True,"pump_stop_confirmed_after_seconds":0},
    {"valve_close_confirmed":True,"valve_link_available":True},
])
def test_invalid_fault_scenarios_are_rejected(changes):
    kwargs = {"fault_kind":"connection_lost", "fault_at_seconds":15, **changes}
    with pytest.raises(ValueError):
        simulate_sequence_fault(FAULT_RUNS, **kwargs)


def test_empty_and_invalid_plans_are_rejected_before_fault_simulation():
    for runs in ([], [ValveRun(1,"opensprinkler-3",0,10)]):
        with pytest.raises(ValueError):
            simulate_sequence_fault(runs, fault_kind="connection_lost", fault_at_seconds=0)


@pytest.mark.parametrize("fault_time", [0, 5, 15, 17, 20, 45])
@pytest.mark.parametrize("valve_link_available", [False, True])
def test_unavailable_local_stop_never_claims_shutdown_or_closes_valves(fault_time, valve_link_available):
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="connection_lost",
        fault_at_seconds=fault_time, local_stop_available=False,
        valve_link_available=valve_link_available)
    assert not result.local_stop_available
    assert result.status == "pump_stop_unconfirmed"
    assert result.pump_stop_confirmed_at_seconds is None
    assert result.unresolved_valves
    assert all(e.at_seconds < fault_time for e in result.events)
    assert result.manual_reset_required and result.simulation_only


@pytest.mark.parametrize("availability", [None, 0, 1, "false"])
def test_local_stop_availability_requires_boolean(availability):
    with pytest.raises(ValueError, match="availability"):
        simulate_sequence_fault(FAULT_RUNS, fault_kind="connection_lost",
            fault_at_seconds=17, local_stop_available=availability)


@pytest.mark.parametrize("delay", [0, 7])
def test_unavailable_local_stop_rejects_injected_stop_confirmation(delay):
    with pytest.raises(ValueError, match="Unavailable local stop"):
        simulate_sequence_fault(FAULT_RUNS, fault_kind="connection_lost",
            fault_at_seconds=17, local_stop_available=False,
            pump_stop_confirmed_after_seconds=delay)


@pytest.mark.parametrize("opening_time", [0, 15])
@pytest.mark.parametrize("timeout", [1, 5, 6, 60, 86400])
def test_open_timeout_suspends_normal_schedule_until_abort(opening_time, timeout):
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="valve_open_unconfirmed",
        fault_at_seconds=opening_time, valve_open_timeout_seconds=timeout)
    deadline = opening_time + timeout
    assert result.fault_at_seconds == deadline
    assert result.uncertain_event.at_seconds == opening_time
    assert result.events[-1] == SequenceEvent(deadline, "pump_off")
    assert all(e.at_seconds < opening_time for e in result.events[:-1])
    assert result.unresolved_valves == tuple(
        (r.controller_id, r.station_number) for r in FAULT_RUNS[:1 if opening_time == 0 else 2])
    assert result.status == "pump_stop_unconfirmed"
    assert result.manual_reset_required and result.simulation_only


def test_timeout_cleanup_delays_are_relative_to_expiry_and_stop_confirmation():
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="valve_open_unconfirmed",
        fault_at_seconds=15, valve_open_timeout_seconds=10,
        pump_stop_confirmed_after_seconds=7, valve_link_available=True,
        valve_close_confirmed=True)
    assert result.fault_at_seconds == 25
    assert result.pump_stop_confirmed_at_seconds == 32
    assert result.events[-3:] == (SequenceEvent(25, "pump_off"),
        SequenceEvent(37, "valve_close", "opensprinkler-1", 0),
        SequenceEvent(37, "valve_close", "opensprinkler-2", 71))
    assert result.status == "stopped" and not result.unresolved_valves
    assert result.manual_reset_required


def test_timeout_with_unavailable_local_stop_keeps_valves_unresolved():
    result = simulate_sequence_fault(FAULT_RUNS, fault_kind="valve_open_unconfirmed",
        fault_at_seconds=15, valve_open_timeout_seconds=60,
        local_stop_available=False, valve_link_available=True)
    assert result.fault_at_seconds == 75
    assert all(e.at_seconds < 15 for e in result.events)
    assert len(result.unresolved_valves) == 2
    assert result.status == "pump_stop_unconfirmed"


@pytest.mark.parametrize("timeout", [-1, True, 1.5, "5", None, 86401])
def test_invalid_open_timeout_is_rejected(timeout):
    with pytest.raises(ValueError, match="timeout"):
        simulate_sequence_fault(FAULT_RUNS, fault_kind="valve_open_unconfirmed",
            fault_at_seconds=0, valve_open_timeout_seconds=timeout)


def test_connection_loss_cannot_be_delayed_by_open_timeout():
    with pytest.raises(ValueError, match="only to an unconfirmed opening"):
        simulate_sequence_fault(FAULT_RUNS, fault_kind="connection_lost",
            fault_at_seconds=15, valve_open_timeout_seconds=5)
