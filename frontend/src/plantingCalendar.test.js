import test from "node:test";
import assert from "node:assert/strict";

import { formatPlantingMonths, plantingTiming } from "./plantingCalendar.js";

test("disjoint cool-season windows stay readable", () => {
  assert.equal(
    formatPlantingMonths("2,3,4,8,9,10"),
    "februar–april in avgust–oktober",
  );
  assert.equal(formatPlantingMonths("1,2,3,4,5,6,7,8,9,10,11,12"), "vse leto");
});

test("Astro remains recommended during a hot outdoor month", () => {
  const timing = plantingTiming({
    planting_method: "direct",
    outdoor_months: "3,4,5,6,7,8,9,10",
    protected_months: "2,3,4,5,6,7,8,9,10,11",
  }, "outdoor", "2026-07-15", "centralna");

  assert.equal(timing.recommended, true);
  assert.equal(timing.monthsLabel, "marec–oktober");
  assert.equal(timing.methodLabel, "setev");
});

test("environment changes the recommendation", () => {
  const socrates = {
    planting_method: "transplant",
    outdoor_months: "5,6",
    protected_months: "4,5,6,7",
  };
  assert.equal(plantingTiming(socrates, "outdoor", "2026-04-10").recommended, false);
  const protectedTiming = plantingTiming(socrates, "protected", "2026-04-10", "primorska");
  assert.equal(protectedTiming.recommended, true);
  assert.equal(protectedTiming.methodLabel, "presajanje");
  assert.match(protectedTiming.regionNote, /Primorskem/);
});
