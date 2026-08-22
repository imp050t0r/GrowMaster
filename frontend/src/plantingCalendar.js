const MONTH_NAMES = [
  "januar", "februar", "marec", "april", "maj", "junij",
  "julij", "avgust", "september", "oktober", "november", "december",
];

export const PLANTING_ENVIRONMENTS = [
  { value: "outdoor", label: "Na prostem" },
  { value: "protected", label: "Neogrevan tunel" },
];

export function parsePlantingMonths(value = "") {
  return [...new Set(String(value).split(",")
    .map((month) => Number(month.trim()))
    .filter((month) => Number.isInteger(month) && month >= 1 && month <= 12))]
    .sort((left, right) => left - right);
}

export function formatPlantingMonths(value = "") {
  const months = parsePlantingMonths(value);
  if (!months.length) return "ni podatka";
  if (months.length === 12) return "vse leto";

  const groups = [];
  let start = months[0];
  let previous = months[0];
  for (const month of months.slice(1)) {
    if (month === previous + 1) {
      previous = month;
      continue;
    }
    groups.push([start, previous]);
    start = month;
    previous = month;
  }
  groups.push([start, previous]);
  return groups.map(([first, last]) => (
    first === last ? MONTH_NAMES[first - 1] : `${MONTH_NAMES[first - 1]}–${MONTH_NAMES[last - 1]}`
  )).join(" in ");
}

export function plantingTiming(variety = {}, environment = "outdoor", dateValue = "", region = "centralna") {
  const field = environment === "protected" ? "protected_months" : "outdoor_months";
  const monthValue = variety[field] || "";
  const months = parsePlantingMonths(monthValue);
  const selectedMonth = Number(String(dateValue || "").slice(5, 7));
  const hasDate = Number.isInteger(selectedMonth) && selectedMonth >= 1 && selectedMonth <= 12;
  const recommended = Boolean(months.length && hasDate && months.includes(selectedMonth));
  const methodLabel = variety.planting_method === "transplant" ? "presajanje" : "setev";
  const environmentLabel = environment === "protected" ? "v neogrevanem tunelu" : "na prostem";
  const regionNotes = {
    primorska: "Na Primorskem je spomladanski začetek pogosto 2–4 tedne zgodnejši, jesenska sezona pa daljša.",
    panonska: "V panonski Sloveniji spremljaj poletno vročino in sušo ter jesensko slano.",
    centralna: "Koledar je nastavljen kot osnovno priporočilo za osrednjo Slovenijo.",
    alpska: "V alpskem svetu je pomlad pogosto 2–4 tedne poznejša, jesensko okno pa krajše.",
  };
  return {
    months,
    monthsLabel: formatPlantingMonths(monthValue),
    hasData: months.length > 0,
    recommended,
    methodLabel,
    environmentLabel,
    regionNote: regionNotes[region] || regionNotes.centralna,
  };
}

export function toleranceLabel(value) {
  return value ? value.charAt(0).toLocaleUpperCase("sl-SI") + value.slice(1) : "ni podatka";
}
