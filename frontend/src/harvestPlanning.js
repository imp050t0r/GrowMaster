export const PROPAGATION_METHODS = [
  { value: "direct", label: "Neposredna setev", shortLabel: "setev" },
  { value: "transplant", label: "Sadike / presajanje", shortLabel: "presajanje" },
];

export const HARVEST_TYPES = [
  { value: "full_size", label: "Cel pridelek / glava" },
  { value: "baby_leaf", label: "Baby leaf · en rez" },
  { value: "outer_leaves", label: "Obiranje zunanjih listov" },
  { value: "cut_and_regrow", label: "Močan rez in ponovno obraščanje" },
];

const parseOptions = (value = "") => [...new Set(String(value).split(",").map((item) => item.trim()).filter(Boolean))];

export function propagationOptions(variety = {}, harvestType = "full_size") {
  let values = parseOptions(variety.cultivation_methods || variety.planting_method || "direct");
  if (["baby_leaf", "cut_and_regrow"].includes(harvestType) && values.includes("direct")) values = ["direct"];
  return PROPAGATION_METHODS.filter((option) => values.includes(option.value));
}

export function harvestOptions(variety = {}) {
  const values = parseOptions(variety.harvest_methods || "full_size");
  return HARVEST_TYPES.filter((option) => values.includes(option.value));
}

export function propagationLabel(value) {
  return PROPAGATION_METHODS.find((option) => option.value === value)?.label || value;
}

export function harvestTypeLabel(value) {
  return HARVEST_TYPES.find((option) => option.value === value)?.label || value;
}

const validNumber = (value, fallback = 0) => {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : fallback;
};

const finiteNumber = (value, fallback = 0) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
};

const dateFromIso = (value) => {
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isNaN(date.getTime()) ? null : date;
};

const addDays = (date, days) => {
  if (!date) return null;
  const result = new Date(date);
  result.setUTCDate(result.getUTCDate() + days);
  return result;
};

const isoDate = (date) => date?.toISOString().slice(0, 10) || null;
const displayDate = (date) => date?.toLocaleDateString("sl-SI", { timeZone: "UTC" }) || "—";

export function calculateHarvestPlan({
  variety = {},
  fieldDate,
  propagationMethod = "direct",
  harvestType = "full_size",
  seasonalDays = 60,
  fallbackBabyDays = 30,
  climateAdjustment = 0,
}) {
  const fieldStart = dateFromIso(fieldDate);
  const nurseryDays = propagationMethod === "transplant" ? validNumber(variety.nursery_days, 28) : 0;
  const directExtra = validNumber(variety.direct_sow_extra_days, 0);
  const baselineMethod = variety.planting_method || propagationMethod;
  const fullDays = Math.max(7, validNumber(seasonalDays, 60));
  const babyDays = Math.max(7, validNumber(variety.days_baby, fallbackBabyDays));
  const outerDays = Math.max(7, validNumber(variety.days_outer_leaf, Math.max(7, fullDays - 15)));
  let stageDays = harvestType === "baby_leaf" || harvestType === "cut_and_regrow"
    ? babyDays
    : harvestType === "outer_leaves" ? outerDays : fullDays;

  if (propagationMethod === "direct" && baselineMethod === "transplant" && !["baby_leaf", "cut_and_regrow"].includes(harvestType)) {
    stageDays += directExtra;
  } else if (propagationMethod === "transplant" && baselineMethod === "direct") {
    stageDays = Math.max(7, stageDays - directExtra);
  }

  const firstHarvestDays = Math.max(7, Math.round(stageDays + finiteNumber(climateAdjustment, 0)));
  const firstHarvest = addDays(fieldStart, firstHarvestDays);
  const regrowthMin = Math.max(1, validNumber(variety.regrowth_interval_min_days, 7));
  const regrowthMax = Math.max(regrowthMin, validNumber(variety.regrowth_interval_max_days, 14));
  const regrowthDays = Math.round((regrowthMin + regrowthMax) / 2);
  const cuts = harvestType === "cut_and_regrow"
    ? Math.max(1, Math.round(validNumber(variety.max_regrowth_cuts, 2)))
    : 1;
  const finalHarvest = addDays(firstHarvest, regrowthDays * Math.max(0, cuts - 1));
  const sowing = propagationMethod === "transplant" ? addDays(fieldStart, -nurseryDays) : fieldStart;
  const transplant = propagationMethod === "transplant" ? fieldStart : null;
  const bedOccupancyDays = firstHarvestDays + regrowthDays * Math.max(0, cuts - 1);

  return {
    nurseryDays,
    firstHarvestDays,
    bedOccupancyDays,
    totalFromSeedDays: bedOccupancyDays + nurseryDays,
    regrowthMin,
    regrowthMax,
    regrowthDays,
    cuts,
    sowingDate: isoDate(sowing),
    sowingDateLabel: displayDate(sowing),
    transplantDate: isoDate(transplant),
    transplantDateLabel: displayDate(transplant),
    firstHarvestDate: isoDate(firstHarvest),
    firstHarvestDateLabel: displayDate(firstHarvest),
    nextCutDateLabel: cuts > 1 ? displayDate(addDays(firstHarvest, regrowthDays)) : null,
    finalHarvestDateLabel: displayDate(finalHarvest),
  };
}
