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
