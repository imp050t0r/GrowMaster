# Smart Irrigation 2026.11.0 compatibility

Reviewed against the stable tag published 2026-11-14:
https://github.com/altmenorg/HAsmartirrigation/releases/tag/v2026.11.0
https://github.com/altmenorg/HAsmartirrigation/blob/v2026.11.0/custom_components/smart_irrigation/services.yaml

GrowMaster remains the irrigation decision maker. Smart Irrigation supplies weather
and calculation inputs; its full controller and direct valve control must remain
disabled in this architecture. OpenSprinkler executes valve commands and the
separate relay is planned for the pump. No hardware executor is enabled here.

`smart_irrigation.set_multiplier` still accepts a sensor target and
`new_multiplier_value`. In 2026.11, an absent target means all zones. GrowMaster
therefore validates the complete Kc batch before opening a transport or changing
pending state. Each request must have exactly one explicit Smart Irrigation sensor
and a finite numeric Kc in GrowMaster's supported 0–2 range. Broad targets, empty
lists, booleans and a substituted watering service are rejected. Existing exact
REST payload tests cover the normal request. The automatic Kc path validates its
whole batch too.

This is a source-contract review and mocked transport verification, not a live
integration test. It does not establish the installed HA/SI version, ET0 sensor
mapping, freshness timestamps or physical watering. Home Assistant 2026.3 or newer
is required by SI. Do not disable its global Calculate and water switch as a
substitute for disabling valve control: calculations are also affected.

`calculate` with `dry_run: true` is a future diagnostic option, not an ET0 sensor:
its zone balance/duration results must not be treated as raw reference ET0.
No calculate, update_weather, water_zone, run_program or credit_watering action
is introduced by this change.
