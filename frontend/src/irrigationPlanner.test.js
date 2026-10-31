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

import { sequencePreviewRuns } from "./irrigationHelpers.js";

const sequenceZones = [
  {id: 1, beds: [{id: 1}]},
  {id: 2, beds: [{id: 3}]},
  {id: 3, beds: [{id: 4}, {id: 5}]},
];

test("sequence request preserves order and includes only bed IDs and numeric durations", () => {
  assert.deepEqual(sequencePreviewRuns([
    {bed_id: 3, run_seconds: "10", controller_id: "injected"},
    {bed_id: 1, run_seconds: "86400"},
  ], sequenceZones), [{bed_id: 3, run_seconds: 10}, {bed_id: 1, run_seconds: 86400}]);
});

test("sequence request rejects shared, missing and repeated beds", () => {
  for (const ids of [[4], [999], [1, 1]]) {
    assert.throws(() => sequencePreviewRuns(ids.map(bed_id => ({bed_id, run_seconds: "10"})), sequenceZones));
  }
});

test("sequence request rejects empty, fractional, nonfinite and out-of-range durations", () => {
  for (const run_seconds of ["", " ", "0", "-1", "1.5", "86401", "NaN", "Infinity"]) {
    assert.throws(() => sequencePreviewRuns([{bed_id: 1, run_seconds}], sequenceZones));
  }
  assert.equal(sequencePreviewRuns([{bed_id: 1, run_seconds: "1"}], sequenceZones)[0].run_seconds, 1);
});

test("sequence request validates the current mapping and limits plan size", () => {
  assert.throws(() => sequencePreviewRuns([], sequenceZones));
  assert.throws(() => sequencePreviewRuns([{bed_id: 1, run_seconds: "10"}], []));
  const zones = Array.from({length: 145}, (_, id) => ({beds: [{id: id + 1}]}));
  const rows = zones.map(zone => ({bed_id: zone.beds[0].id, run_seconds: "1"}));
  assert.equal(sequencePreviewRuns(rows.slice(0, 144), zones).length, 144);
  assert.throws(() => sequencePreviewRuns(rows, zones));
});
