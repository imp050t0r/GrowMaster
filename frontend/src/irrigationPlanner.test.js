import test from "node:test";
import assert from "node:assert/strict";
import { cropIdForBed, dailyBedStates } from "./irrigationHelpers.js";

test("selecting a bed resolves its currently active crop", () => {
  const bed = { current_planting: { crop: "Solata" } };
  assert.equal(cropIdForBed(bed, [{ id: 3, name: "Koriander" }, { id: 9, name: "solata" }]), "9");
});

test("an empty bed or unlisted crop does not guess a crop", () => {
  assert.equal(cropIdForBed({ current_planting: null }, [{ id: 1, name: "Solata" }]), "");
  assert.equal(cropIdForBed({ current_planting: { crop: "Unknown" } }, [{ id: 1, name: "Solata" }]), "");
});

test("daily bed review calls out active beds with no saved calculation", () => {
  const beds = [
    { id: 1, name: "A1", current_planting: { crop: "Solata" } },
    { id: 2, name: "A2", current_planting: { crop: "Koriander" } },
  ];
  const states = dailyBedStates(beds, [{ id: 1, name: "Solata" }, { id: 2, name: "Koriander" }],
    { crops: [{ crop_id: 1 }, { crop_id: 2 }], beds: [{ bed_id: 1 }] },
    [{ bed_id: 1, status: "hold" }]);
  assert.equal(states[0].needsCalculation, false);
  assert.equal(states[1].needsCalculation, true);
  assert.equal(states[1].hasBedProfile, false);
});
