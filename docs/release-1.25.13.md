# GrowMaster 1.25.13

- Added **SHRANI POVEZAVO VENTILA** to save a bed's Home Assistant OpenSprinkler station without inventing soil or flow measurements.
- An incomplete bed profile continues to block irrigation calculation; saving the station does not contact Home Assistant or start watering.
- Aligns station action previews with the installed `opensprinkler.run` service.
- Includes advisory daily sequence previews, fault simulations and manual fertilization records developed on PR #89.
- Pump sequencing remains simulation-only; this release does not validate or enable live pump hardware.
- Migration 0021 stores preliminary station assignments. Backups preserve these mappings and older backups remain supported.

Validation: 543 backend tests passed (542 in the full suite plus the corrected schema integration test rerun), 7 frontend tests passed, frontend build passed. Live hardware was not tested.
