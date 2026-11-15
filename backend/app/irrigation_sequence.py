"""Pure preview of a local shared-pump sequence; never sends hardware commands.

Durations are exclusive watering dwell times. Transition overlap and final
drain-down are additional time, not measured irrigation or delivery guarantees.
"""
from dataclasses import dataclass
from typing import Iterable, Literal


DELAY_SECONDS = 5


@dataclass(frozen=True)
class ValveRun:
    bed_id: int
    controller_id: str
    station_number: int
    run_seconds: int


@dataclass(frozen=True)
class SequenceEvent:
    at_seconds: int
    action: Literal["valve_open", "pump_on", "pump_off", "valve_close"]
    controller_id: str | None = None
    station_number: int | None = None


def preview_sequence(runs: Iterable[ValveRun]) -> tuple[SequenceEvent, ...]:
    """Validate the whole plan before returning an immutable simulated timeline.

    Starts with pump off and all valves closed. One bed per valve, at most
    two controllers with 72 zero-based stations each. No persistence, retries,
    networking or automatic execution; acknowledgement/fault handling belongs
    to a future local executor, not this idealized preview.
    """
    runs = tuple(runs)
    beds = set()
    valves = set()
    for run in runs:
        if type(run.bed_id) is not int or run.bed_id <= 0:
            raise ValueError("Bed ID must be a positive integer.")
        if run.controller_id not in ("opensprinkler-1", "opensprinkler-2"):
            raise ValueError("Unknown OpenSprinkler controller.")
        if type(run.station_number) is not int or not 0 <= run.station_number < 72:
            raise ValueError("Station number must be an integer from 0 to 71.")
        if type(run.run_seconds) is not int or not 1 <= run.run_seconds <= 86400:
            raise ValueError("Run duration must be an integer from 1 to 86400 seconds.")
        valve = (run.controller_id, run.station_number)
        if run.bed_id in beds or valve in valves:
            raise ValueError("Each bed and physical valve may occur only once per plan.")
        beds.add(run.bed_id)
        valves.add(valve)
    if not runs:
        return ()

    events = []

    def valve_event(at_seconds, action, run):
        events.append(SequenceEvent(at_seconds, action, run.controller_id, run.station_number))

    current = runs[0]
    valve_event(0, "valve_open", current)
    elapsed = DELAY_SECONDS
    events.append(SequenceEvent(elapsed, "pump_on"))
    for following in runs[1:]:
        elapsed += current.run_seconds
        valve_event(elapsed, "valve_open", following)
        elapsed += DELAY_SECONDS
        valve_event(elapsed, "valve_close", current)
        current = following
    elapsed += current.run_seconds
    events.append(SequenceEvent(elapsed, "pump_off"))
    valve_event(elapsed + DELAY_SECONDS, "valve_close", current)
    return tuple(events)


@dataclass(frozen=True)
class FaultSimulation:
    """Command preview and injected confirmations, never observed hardware state."""
    events: tuple[SequenceEvent, ...]
    fault_kind: Literal["valve_open_unconfirmed", "connection_lost"]
    fault_at_seconds: int
    uncertain_event: SequenceEvent | None
    pump_stop_confirmed_at_seconds: int | None
    unresolved_valves: tuple[tuple[str, int], ...]
    status: Literal["pump_stop_unconfirmed", "valves_unconfirmed", "stopped"]
    simulation_only: bool = True
    manual_reset_required: bool = True
    local_stop_available: bool = True


def simulate_sequence_fault(
    runs: Iterable[ValveRun],
    *,
    fault_kind: Literal["valve_open_unconfirmed", "connection_lost"],
    fault_at_seconds: int,
    pump_stop_confirmed_after_seconds: int | None = None,
    valve_link_available: bool = False,
    valve_close_confirmed: bool = False,
    local_stop_available: bool = True,
    valve_open_timeout_seconds: int = 0,
) -> FaultSimulation:
    """Inject one fault into the ideal timeline and preview conservative abort.

    Events strictly before the fault are assumed acknowledged. A command exactly
    at the fault is uncertain and may have reached the device. Connection loss
    can also occur between commands. Stop/close confirmations are explicit test
    inputs, not timers, HA responses or proof of physical position/pressure.
    """
    events = preview_sequence(runs)
    if fault_kind not in ("valve_open_unconfirmed", "connection_lost"):
        raise ValueError("Unsupported simulated fault.")
    if not events or type(fault_at_seconds) is not int or not 0 <= fault_at_seconds <= events[-1].at_seconds:
        raise ValueError("Fault time must be an integer within a nonempty sequence.")
    if (pump_stop_confirmed_after_seconds is not None
            and (type(pump_stop_confirmed_after_seconds) is not int or pump_stop_confirmed_after_seconds < 0)):
        raise ValueError("Pump confirmation delay must be a nonnegative integer or None.")
    if type(valve_link_available) is not bool or type(valve_close_confirmed) is not bool:
        raise ValueError("Simulated link and confirmation flags must be booleans.")
    if valve_close_confirmed and (not valve_link_available or pump_stop_confirmed_after_seconds is None):
        raise ValueError("Valve closure cannot be confirmed without pump-stop confirmation and valve control.")
    if type(local_stop_available) is not bool:
        raise ValueError("Local stop availability must be a boolean.")
    if not local_stop_available and pump_stop_confirmed_after_seconds is not None:
        raise ValueError("Unavailable local stop cannot produce a simulated stop confirmation.")
    if type(valve_open_timeout_seconds) is not int or not 0 <= valve_open_timeout_seconds <= 86400:
        raise ValueError("Valve-open timeout must be an integer from 0 to 86400 seconds.")
    if fault_kind != "valve_open_unconfirmed" and valve_open_timeout_seconds:
        raise ValueError("Valve-open timeout applies only to an unconfirmed opening.")
    uncertain = next((event for event in events if event.at_seconds == fault_at_seconds), None)
    if fault_kind == "valve_open_unconfirmed" and (uncertain is None or uncertain.action != "valve_open"):
        raise ValueError("An unconfirmed opening must coincide with a valve-open command.")

    history = []
    possible_open = set()
    for event in events:
        if event.at_seconds >= fault_at_seconds:
            break
        history.append(event)
        valve = (event.controller_id, event.station_number)
        if event.action == "valve_open":
            possible_open.add(valve)
        elif event.action == "valve_close":
            possible_open.remove(valve)
    if uncertain is not None and uncertain.action == "valve_open":
        # The request may have arrived even though its acknowledgement did not.
        possible_open.add((uncertain.controller_id, uncertain.station_number))

    # No normal commands run while the opening is awaiting acknowledgement.
    # fault_at_seconds selects the opening request; abort starts at its deadline.
    abort_at = fault_at_seconds + valve_open_timeout_seconds
    # Discard the remaining watering schedule; never retry the uncertain command.
    # This is a request for an independent local stop, not a successful stop.
    if local_stop_available:
        history.append(SequenceEvent(abort_at, "pump_off"))
    confirmed_at = None
    status = "pump_stop_unconfirmed"
    if pump_stop_confirmed_after_seconds is not None:
        confirmed_at = abort_at + pump_stop_confirmed_after_seconds
        if valve_link_available:
            for controller_id, station_number in sorted(possible_open):
                history.append(SequenceEvent(confirmed_at + DELAY_SECONDS, "valve_close", controller_id, station_number))
            if valve_close_confirmed:
                possible_open.clear()
        status = "valves_unconfirmed" if possible_open else "stopped"
    return FaultSimulation(tuple(history), fault_kind, abort_at, uncertain,
                           confirmed_at, tuple(sorted(possible_open)), status,
                           local_stop_available=local_stop_available)
