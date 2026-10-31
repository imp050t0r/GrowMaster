# Permanent irrigation valve groups — implementation contract

GrowMaster is the sole irrigation decision maker: crop planning, zone water
demand, durations and authorization. Ecowitt WS90 supplies weather observations;
Home Assistant Smart Irrigation supplies ET0/weather inputs, not an independent
watering schedule. Two OpenSprinkler v4 controllers operate up to 72 outputs each.
A common pump and frequency inverter serve both controllers. There are currently
no flow or pressure sensors; do not assume pressure regulation or measured delivery.
Timing and pump protection must execute locally, independently of cloud availability.

## Physical mapping
- A valve zone identifies a controller and station number.
- Each bed has at most one permanent valve assignment.
- The confirmed installation uses one bed per valve (up to 144 independent beds).
- Existing shared-valve records and planting rules below remain supported for compatibility.
- Mapping changes require explicit administrative reconfiguration, not crop rotation.
- A shared valve is one planting unit: same crop, variety, sowing date and transplant date.
- A proposal must cover every bed assigned to that valve; reject partial proposals.
- Keep separate bed harvest, cost, profitability and rotation histories.
- Crop suggestions must be acceptable under the rotation history of **every** bed.

## Irrigation decision and execution (future integration)
- GrowMaster derives development stage from planting date, crop/variety and weather.
- ET0 from HA Smart Irrigation/weather station is an input, not a second scheduler.
- Estimate crop ET from stage-dependent Kc, rain, water ledger and soil measurements.
- Convert a shared valve's demand to litres/time using calibrated emitter flow.
- Emitter specifications/calibration estimate delivery; there is no flow meter.
- Do not send real valve commands until hydraulic, timing and pump protections pass tests.
- A local controller must handle opening the first valve 5 seconds before pump-on, 5-second overlap at
  zone transitions, and pump-off-before-final-group-closes (5 seconds).
- Validate the final 5-second delay against the actual VFD ramp-down before live use;
  elapsed time alone is not confirmation of a stopped pump or an open valve.
- On stale weather inputs, lost connectivity or uncertain
  valve state, fail safe rather than improvising watering.
- Initial hardware integration is simulation-only.

## Work remaining
- Replace the legacy Smart Irrigation duration/Kc synchronization path in
  `irrigation_routes.py` with GrowMaster-owned decisions from weather/ET0 inputs.
  The existing automatic runner is not the shared-pump executor described here.
- Integrate estimated delivery and local handoff.
- Connect actual HA entities to the normalized weather input below; their entity
  IDs and ET0 period/attribute mapping have not yet been configured or verified.
- Implement local acknowledgements, timeout/abort handling, restart recovery and
  independent pump protection before connecting the preview to hardware.
- Add integration tests and hardware-in-the-loop safety acceptance tests.

## Implemented sequence preview (simulation only)

`backend/app/irrigation_sequence.py::preview_sequence` accepts ordered `ValveRun`
values and returns an immutable tuple of timestamped events. It has no network,
database, scheduler or hardware dependencies and is not wired to the live runner.
It assumes an initially stopped pump and closed valves; it does not inspect them.
The complete input is validated before any timeline is returned: positive bed IDs,
the existing `opensprinkler-1`/`opensprinkler-2` IDs, station numbers 0–71,
integer dwell durations 1–86400 seconds, and no repeated bed or physical valve.
An empty plan returns no events. Shared-bed valve plans are not accepted by this
new preview; the legacy mapping API is unchanged.

Duration means exclusive watering dwell, excluding the extra overlap and shutdown
time. Incoming valves also remain open during the five-second transition; outgoing
valves remain open for five additional seconds. This must be accounted for when
future demand planning estimates water application. No measured water volume is claimed.

For two beds with dwell times 10 and 20 seconds on different controllers:

| Time (s) | Simulated event |
| --- | --- |
| 0 | Open first valve |
| 5 | Start common pump |
| 15 | Open second valve, keep first open |
| 20 | Close first valve, keep pump running |
| 40 | Stop common pump |
| 45 | Close second valve |

The preview describes ideal successful timing only. It is not a safe live
executor: failed valve operations, cancellation, connectivity loss and VFD faults
require local handling and hardware acceptance testing. No deployment setting is
enabled by importing or calling this function.

Run the focused tests from the repository root with `PYTHONPATH=backend python -m
pytest -q backend/tests/test_irrigation_sequence.py` (set `PYTHONPATH` using the
shell's environment syntax on Windows).

## Normalized weather input (advisory calculation only)

`POST /api/irrigation/calculate` and `PUT /api/irrigation/daily` accept an optional
`weather` object alongside the existing bed, crop, stage and water-balance fields:

```json
{
  "source": "ha_smart_irrigation_ws90",
  "day": "2026-10-25",
  "eto_mm": 3.2,
  "unit": "mm",
  "observed_at": "2026-10-25T08:00:00+01:00",
  "calculated_at": "2026-10-25T08:05:00+01:00"
}
```

The example timestamps must be replaced with actual current source timestamps.
`day` declares the daily ET0 accumulation period and must equal the requested
balance day. `observed_at` is the timestamp of the WS90 observation used in the
ET0 calculation; `calculated_at` is the Smart Irrigation calculation timestamp.
Do not substitute an HA fetch/update timestamp or a watering-duration sensor.
This API accepts a normalized daily depth in millimetres, not an hourly rate,
instantaneous reading, crop ETc, or seconds of watering. A future HA adapter must
verify these source semantics rather than infer them from an entity name.

Both timestamps require an explicit timezone and must be between now and six
hours ago, inclusive, at calculation time. Observation cannot follow calculation.
The whole weather object is mandatory when supplied; missing/unavailable ET0 is
rejected, while numeric zero is valid. ET0 must be a finite JSON number in 0–30 mm.
Unknown fields (including watering commands/durations) and other units are rejected.
Failures return HTTP 422 and do not overwrite a stored daily report.

Top-level `eto_mm` may be omitted/null or must match the weather ET0. The existing
required `weather_source` field is replaced in the report with the normalized
source identifier. Reports retain the complete weather object for inspection.
GrowMaster applies its own crop Kc and computes demand using the existing balance;
stage, opening depletion, effective rain and applied irrigation remain explicit
caller inputs. WS90 rainfall is not automatically treated as effective rain.

This is ingestion and freshness validation, not independent source authentication
or automatic HA polling. No sensor configuration, live command, scheduler setting
or water-ledger application is created. Reports remain advisory with
`automatic_execution: false`. Existing requests without `weather` retain manual
input behavior; the legacy automatic runner remains separate and still needs the
architecture migration described above.

## Read-only Home Assistant weather adapter

`GET /api/irrigation/home-assistant/weather?entity_id=sensor.growmaster_et0&day=2026-10-25`
reads one entity using the existing encrypted HA connection (or its existing
URL/token environment fallback). The requested sensor must be explicitly listed
in the existing `HOME_ASSISTANT_WEATHER_ENTITIES` setting. This endpoint makes
one HA state GET with an eight-second timeout and redirects disabled. It neither
calls HA services nor writes reports, configuration or irrigation state.

The entity must expose this **GrowMaster adapter contract**. These attribute
names are not claimed to exist in the native Smart Irrigation integration:

| HA state field | Meaning |
| --- | --- |
| `entity_id` | Exactly the requested sensor ID |
| `state` | Numeric daily reference ET0 depth, 0–30 inclusive; numeric zero is valid |
| `attributes.unit_of_measurement` | `mm` |
| `attributes.growmaster_source` | `ha_smart_irrigation_ws90` |
| `attributes.growmaster_day` | ET0 balance day, ISO date; must match the requested day |
| `attributes.growmaster_observed_at` | Timestamp of the actual WS90 observation used |
| `attributes.growmaster_calculated_at` | Timestamp of the ET0 calculation using that observation |

The two source timestamps use the same timezone, ordering and six-hour freshness
validation as the calculation API. HA `last_updated` is deliberately ignored:
re-reading or refreshing a stale value must not make the underlying weather fresh.
Missing attributes, unavailable values, duration/rate units, mismatched entities
or periods, malformed responses and upstream HTTP/network failures return 502.
An unapproved entity or future request day returns 422; missing HA connection
returns 503. Upstream bodies and credentials are not included in error responses.

A successful response contains `entity_id`, `weather` (the normalized object
accepted by `/calculate` and `/daily`) and `automatic_execution: false`. The caller
can pass `weather` unchanged to an advisory calculation, which rechecks freshness.
Reading weather alone never records irrigation or changes an existing report.

Installation status: Smart Irrigation is installed, but complete weather/ET0
inputs are not yet available. No real entity mapping or WS90 connection has been
verified. A later installation step must map verified ET0 and source timestamps
to this contract, for example through a dedicated HA sensor. Do not invent source
timestamps, substitute HA fetch time, or label a duration/rain sensor as ET0.
The adapter has mocked integration tests; it is not live-hardware acceptance.

## Sequence preview API using permanent mappings

`POST /api/irrigation/sequence-preview` exposes the pure sequence simulator through
the existing irrigation API. Example request:

```json
{"runs": [{"bed_id": 1, "run_seconds": 10}, {"bed_id": 3, "run_seconds": 20}]}
```

Each run supplies only a bed ID and an exclusive dwell duration (strict integers,
1–86400 seconds). The server resolves controller/station from the permanent valve
mapping for the current farm. It preserves caller order and accepts at most 144
runs; an empty plan returns no events and zero total time. Caller-supplied hardware
addresses and execution flags are rejected. This does not derive irrigation demand
from weather or authorize the supplied durations.

Missing/foreign beds or mappings, cross-farm valve references, shared-bed valves
and unsupported controller/station mappings return 409. Duplicate beds, invalid
durations and oversized requests return 422. All membership is checked, including
beds on a selected valve that were not included in the request. Shared-valve
planting features remain unchanged; this preview targets one bed per valve.

The response includes `simulation_only: true`, `automatic_execution: false`, the
resolved `runs` with each valve's `valve_enabled` state, timestamped `events` and
`total_seconds` including startup, overlap and shutdown delays. Disabled valves
can be simulated and stay disabled. For dwell times 10 and 20 seconds, the total
is 45 seconds, following the timeline above. No database writes, automation-state
writes, HA calls or hardware commands are performed.

This API is an engineering preview, not a runnable or approved watering plan.
It does not validate water demand, configured runtime limits, hydraulic capacity,
weather availability or actual pump/valve state. Do not send its events directly
to hardware. Local acknowledgement/fault handling and hardware acceptance testing
are still required before execution can be implemented.

## Sequence preview in the irrigation screen

The existing valve section now includes **Predogled zaporedja namakanja – simulacija**.
Choose beds with individual permanent valve mappings, enter dwell durations in
seconds, and use **Prej**, **Pozneje** or **Odstrani** to edit the order. Disabled
valves are available for simulation. Shared-bed valves are excluded.

**Prikaži časovnico** calls only the sequence-preview endpoint. The result shows
elapsed seconds, valve/pump events, mapped bed/controller/output and total elapsed
time including delays. Editing the plan clears the old preview. Refreshing valve
mappings clears the plan and ignores an outstanding response for the old mappings.
No execution button is provided. Weather inputs are not required for this manual
engineering simulation; it is not a watering recommendation.

## GrowMaster daily sequence draft

`GET /api/irrigation/daily-sequence-preview?day=2026-10-26` assembles today's
advisory plan for all active beds on the current farm, ordered by bed ID. It
recalculates demand with GrowMaster's existing water-balance/Kc calculation;
Smart Irrigation watering durations are not read. This endpoint requires no HA
connection and performs no network calls or database writes.

Every active bed requires exactly one active planting and a saved daily report
no older than six hours with matching bed, crop, day and current growth stage.
The report must also identify the same active planting; saving `/daily` now
records `active_planting_id`. Older reports without this identity require a fresh
save. Current crop/bed profiles and bed area must match the saved snapshot, and
the normalized ET0/WS90 observation and calculation must still be fresh. Soil
sensor mode is blocked until that mode has its own validated daily handoff.
Opening depletion, effective rain and already applied water remain explicit
report inputs; this does not implement automatic weather collection or water-ledger
carry-forward. A dry-run draft remains subject to manual review.

Beds whose recalculated decision is `hold` do not enter the sequence. For beds
requiring irrigation, `estimated_run_seconds` is computed from unrounded demand
and configured emitter flow, rounded down to whole seconds. The planner subtracts
five seconds for each adjacent transition, so a middle valve accounts for both
overlaps. The supplied dwell must remain positive. The full valve-open interval
(dwell plus ten seconds, including startup/shutdown delays) must fit the configured
`max_run_seconds`. Any impossible duration blocks the complete plan rather than
silently trimming a dose or dropping a bed.

The response has `status` (`draft`, `no_irrigation` or `blocked`), per-bed `rows`
with decisions/reasons, and resolved `runs`, `events`, and `total_seconds`.
Mapping validation reuses the manual preview's one-bed-per-valve and farm checks.
If any bed or mapping is blocked, `runs` and `events` are empty. A draft can include
disabled valves for inspection and is always `simulation_only: true`,
`automatic_execution: false`, `requires_manual_review: true`.

`estimated_litres` models time with the pump on, including overlap. Actual flow
while two valves are open and water during VFD ramp-down are not measured and
require hardware calibration. The draft is not an execution record, cannot
prevent repeat watering, does not change the legacy runner and is not sent to
OpenSprinkler. Its API is implemented; a daily-plan UI and local execution remain
separate integration steps.

## Fault injection for the local-sequencer simulation

`backend/app/irrigation_sequence.py::simulate_sequence_fault` previews abort
behavior without timers, network access, database writes or hardware commands.
It accepts the same validated `ValveRun` plan as the ideal preview, plus:

- `fault_kind`: `valve_open_unconfirmed` or `connection_lost`.
- `fault_at_seconds`: an integer inside the nonempty ideal timeline. An unconfirmed
  opening must coincide with an opening event; connection loss may occur during
  a dwell, during overlap, or exactly when any command is attempted.
- `pump_stop_confirmed_after_seconds`: explicit simulated confirmation delay after
  the fault, or `None` (default) when stopping is not confirmed.
- `valve_link_available`: whether valve control is available during cleanup,
  default false. After connection loss this requires an explicit simulated recovery.
- `valve_close_confirmed`: whether the cleanup close requests are all confirmed,
  default false. It requires a confirmed pump stop and available valve control.

Events strictly before the fault are assumed acknowledged. A command exactly at
fault time is returned separately as `uncertain_event`: it may have reached the
device. An uncertain opening therefore adds that valve to the potentially open
set. An uncertain close never removes it. No uncertain watering command is retried,
no later opening/start is issued, and the remaining watering schedule is discarded.

At fault time the trace requests `pump_off`, representing the requirement for an
independent local stop path. Sending this request is **not** stop confirmation.
Without explicit confirmation, status is `pump_stop_unconfirmed` and no cleanup
valve-close requests are produced, even if valve communication is available.
After confirmation, cleanup waits five seconds **from confirmation**, not from the
stop request. With valve control available it requests closure of all potentially
open valves. Without valve control it preserves them and reports
`valves_unconfirmed`. A close request alone also leaves valves unresolved.
Only explicit simulated close confirmation produces `stopped` with no unresolved
valves. Every result retains `simulation_only: true` and
`manual_reset_required: true`; successful cleanup never resumes watering.

Example: if the second valve's opening at 15 seconds is unconfirmed and the pump
stop is confirmed seven seconds later, closure requests can occur no earlier than
27 seconds. Both the previous valve and possibly opened new valve remain unresolved
until cleanup is confirmed. A missing pump-stop confirmation leaves both untouched.

These are injected test outcomes, not observed physical state or an assurance of
safe pressure. The simulator does not implement acknowledgement deadlines,
watchdog hardware, persistent restart recovery, partial close acknowledgements or
VFD fault handling. The five-second ramp-down allowance still requires hardware
validation. If communication loss also disables the local pump-stop path, the
simulation must use no stop confirmation; it must not claim a safe stop.
The fault simulator is not wired to the live runner, API or UI.


### Loss of the local pump-stop path

The fault simulator also accepts `local_stop_available` (strict boolean, default
`true` to preserve existing simulations). This is an injected assumption, not a
hardware capability check. With `false`, it produces no abort `pump_off` command,
rejects any injected pump-stop confirmation, and keeps status
`pump_stop_unconfirmed`. Valve communication recovery alone cannot permit cleanup:
all potentially open valves remain unresolved and manual reset is still required.
The result exposes `local_stop_available` so callers can distinguish an unavailable
stop path from an issued but unconfirmed stop request.

No independent local pump-stop implementation has been validated by these tests.
Before live execution, loss of the HA/OpenSprinkler connection must be tested
against the actual local stop mechanism and VFD feedback. An available command
path alone remains insufficient evidence that the pump has physically stopped.


### Simulated opening acknowledgement timeout

For `valve_open_unconfirmed`, `valve_open_timeout_seconds` sets the injected wait
for an acknowledgement that never arrives (integer 0..86400; default 0 preserves
immediate-fault previews). This is a simulation range, not a recommended hardware
timeout. The input `fault_at_seconds` still selects the opening request in the
ideal timeline. The result's `fault_at_seconds` records the abort deadline:
request time plus timeout. `uncertain_event.at_seconds` preserves request time.

During this wait no subsequent normal commands are emitted. At the first valve,
the pump never starts. At a transition the previous valve stays potentially open;
the simulator never executes its scheduled close while waiting for the new valve.
The deadline may exceed the ideal timeline because that timeline is suspended.
Pump-stop confirmation delay starts at timeout expiry; the five-second cleanup
wait starts at stop confirmation. For example, opening at 15, timeout 10 and stop
confirmation delay 7 yield stop request at 25, confirmation at 32 and closes at 37.
Loss of the local stop path still leaves valves unresolved without cleanup.

Connection loss is handled immediately and rejects a nonzero opening timeout.
This models only missing acknowledgements: no real timer, timely/late response
processing, physical-position feedback or live executor is introduced.
