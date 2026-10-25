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
