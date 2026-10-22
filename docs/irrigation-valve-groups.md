# Permanent irrigation valve groups — implementation contract

GrowMaster owns crop planning, zone water demand and authorization of irrigation.
Home Assistant executes an approved plan; OpenSprinkler controls valves.
The pump VFD autonomously regulates pressure. Never drive a pump solely
through a remote/cloud command without independent local fail-safe protection.

## Physical mapping
- A valve zone identifies a controller and station number.
- Each bed has at most one permanent valve assignment.
- Multiple beds may share a valve.
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
- With one common flow meter, simultaneous zones have only aggregate measured flow.
- Do not send real valve commands until hydraulic, timing and pump protections pass tests.
- A local controller must handle open-valve-before-pump, 5-second overlap at
  zone transitions, and pump-off-before-final-group-closes (5 seconds).
- If the VFD ramps down, confirm safe flow/pressure before closing valves.
- On stale sensors, lost connectivity, flow/pressure anomalies or uncertain
  valve state, fail safe rather than improvising watering.
- Initial hardware integration is simulation-only.

## Work remaining
- Add transactional group-planting endpoint with atomic validation.
- Enforce group constraints for *all* planting and crop-plan mutation paths.
- Expose mapping administration and group-level crop suggestions in the UI.
- Integrate weather/ET0, sensor quality, zone flow calibration and HA handoff.
- Add integration tests and hardware-in-the-loop safety acceptance tests.
