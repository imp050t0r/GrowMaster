import test from "node:test";
import assert from "node:assert/strict";
import { calculateHarvestPlan, harvestOptions, propagationOptions } from "./harvestPlanning.js";

const endive = {
  planting_method: "transplant",
  cultivation_methods: "direct,transplant",
  harvest_methods: "full_size,baby_leaf,outer_leaves,cut_and_regrow",
  nursery_days: 25,
  direct_sow_extra_days: 18,
  days_baby: 35,
  days_outer_leaf: 62,
  regrowth_interval_min_days: 5,
  regrowth_interval_max_days: 14,
  max_regrowth_cuts: 3,
};

test("endive distinguishes nursery time from bed occupancy", () => {
  const transplant = calculateHarvestPlan({ variety: endive, fieldDate: "2026-08-01", propagationMethod: "transplant", seasonalDays: 80 });
  const direct = calculateHarvestPlan({ variety: endive, fieldDate: "2026-08-01", propagationMethod: "direct", seasonalDays: 80 });
  assert.equal(transplant.sowingDate, "2026-07-07");
  assert.equal(transplant.transplantDate, "2026-08-01");
  assert.equal(transplant.firstHarvestDays, 80);
  assert.equal(transplant.totalFromSeedDays, 105);
  assert.equal(direct.firstHarvestDays, 98);
});

test("baby leaf and regrowth use distinct harvest schedules", () => {
  const baby = calculateHarvestPlan({ variety: endive, fieldDate: "2026-09-01", propagationMethod: "direct", harvestType: "baby_leaf", seasonalDays: 92 });
  const regrowth = calculateHarvestPlan({ variety: endive, fieldDate: "2026-09-01", propagationMethod: "direct", harvestType: "cut_and_regrow", seasonalDays: 92 });
  assert.equal(baby.firstHarvestDays, 35);
  assert.equal(baby.cuts, 1);
  assert.equal(regrowth.cuts, 3);
  assert.equal(regrowth.regrowthDays, 10);
  assert.equal(regrowth.bedOccupancyDays, 55);
  assert.equal(regrowth.nextCutDateLabel, "16. 10. 2026");
});

test("warmer regional adjustment can shorten the estimate", () => {
  const plan = calculateHarvestPlan({
    variety: endive,
    fieldDate: "2026-08-01",
    propagationMethod: "transplant",
    seasonalDays: 80,
    climateAdjustment: -12,
  });
  assert.equal(plan.firstHarvestDays, 68);
  assert.equal(plan.firstHarvestDate, "2026-10-08");
});

test("catalog capabilities control the choices", () => {
  assert.deepEqual(harvestOptions(endive).map((option) => option.value), ["full_size", "baby_leaf", "outer_leaves", "cut_and_regrow"]);
  assert.deepEqual(propagationOptions(endive, "full_size").map((option) => option.value), ["direct", "transplant"]);
  assert.deepEqual(propagationOptions(endive, "baby_leaf").map((option) => option.value), ["direct"]);
});
