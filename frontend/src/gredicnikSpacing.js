export const GREDICNIK_MODES = [
  { value: "standard", label: "Standardno" },
  { value: "seeder6", label: "6 vrst" },
  { value: "seeder12", label: "12 vrst" },
  { value: "baby6", label: "Baby leaf · 6 vrst" },
  { value: "baby12", label: "Baby leaf · 12 vrst" },
];

const normalize = (value = "") => value.toLocaleLowerCase("sl-SI").trim();
const includesAny = (value, keywords) => keywords.some((keyword) => value.includes(keyword));
const roundOne = (value) => Math.round(value * 10) / 10;

const DEFAULT_PROFILE = {
  plantCm: 25,
  rowCm: 30,
  rows: 3,
  system: "paperpot",
  note: "Za novo ali neznano sorto uporabi začetno priporočilo in ga po prvi žetvi popravi.",
};

const CROP_PROFILES = [
  { crops: ["paradiž"], plantCm: 45, rowCm: 40, rows: 2, system: "paperpot", large: true },
  { crops: ["paprik", "feferon", "indijski čili"], plantCm: 35, rowCm: 35, rows: 2, system: "paperpot", large: true },
  { crops: ["jajčevec", "indijski jajčevec"], plantCm: 45, rowCm: 40, rows: 2, system: "paperpot", large: true },
  { crops: ["kumara"], plantCm: 35, rowCm: 40, rows: 2, system: "paperpot", large: true },
  { crops: ["bučka", "rebrasta bučka", "gobasta bučka"], plantCm: 60, rowCm: 70, rows: 1, system: "manual", large: true },
  { crops: ["buča", "lauki", "karela", "tinda", "voščena buča"], plantCm: 90, rowCm: 90, rows: 1, system: "manual", large: true },
  { crops: ["solata"], plantCm: 25, rowCm: 25, rows: 3, system: "paperpot" },
  { crops: ["endivija", "cikorija"], plantCm: 25, rowCm: 25, rows: 3, system: "paperpot" },
  { crops: ["radič"], plantCm: 25, rowCm: 25, rows: 3, system: "paperpot" },
  { crops: ["zelje", "pekinško zelje"], plantCm: 40, rowCm: 40, rows: 2, system: "paperpot", large: true },
  { crops: ["cvetača", "brokoli"], plantCm: 40, rowCm: 40, rows: 2, system: "paperpot", large: true },
  { crops: ["koleraba"], plantCm: 15, rowCm: 20, rows: 4, system: "paperpot" },
  { crops: ["pak choi", "tatsoi", "komatsuna", "choi sum", "kailan"], plantCm: 15, rowCm: 20, rows: 4, system: "paperpot" },
  { crops: ["mizuna", "mibuna", "azijska gorčica", "shungiku"], plantCm: 10, rowCm: 15, rows: 5, system: "direct" },
  { crops: ["rukola", "divja rukola"], plantCm: 2.5, rowCm: 15, rows: 5, system: "direct" },
  { crops: ["korenje"], plantCm: 2.5, rowCm: 15, rows: 5, system: "direct" },
  { crops: ["redkvica"], plantCm: 2.5, rowCm: 15, rows: 5, system: "direct" },
  { crops: ["rdeča pesa", "mladi listi rdeče pese"], plantCm: 7.5, rowCm: 20, rows: 4, system: "direct" },
  { crops: ["daikon", "japonska repa", "repa"], plantCm: 10, rowCm: 20, rows: 4, system: "direct" },
  { crops: ["malabarska špinača"], plantCm: 30, rowCm: 35, rows: 2, system: "paperpot", large: true },
  { crops: ["špinača", "palak"], plantCm: 7.5, rowCm: 20, rows: 4, system: "direct" },
  { crops: ["motovilec"], plantCm: 5, rowCm: 15, rows: 5, system: "direct" },
  { crops: ["peteršilj", "koriander", "methi"], plantCm: 5, rowCm: 20, rows: 4, system: "direct" },
  { crops: ["čebula"], plantCm: 10, rowCm: 20, rows: 4, system: "direct" },
  { crops: ["por"], plantCm: 15, rowCm: 20, rows: 4, system: "paperpot" },
  { crops: ["česen"], plantCm: 15, rowCm: 20, rows: 4, system: "manual" },
  { crops: ["fižol", "edamame"], plantCm: 10, rowCm: 25, rows: 3, system: "direct" },
  { crops: ["grah"], plantCm: 5, rowCm: 20, rows: 4, system: "direct" },
  { crops: ["bob"], plantCm: 20, rowCm: 30, rows: 3, system: "direct" },
  { crops: ["krompir"], plantCm: 30, rowCm: 60, rows: 1, system: "manual" },
  { crops: ["blitva"], plantCm: 25, rowCm: 30, rows: 3, system: "paperpot" },
  { crops: ["zelena"], plantCm: 25, rowCm: 25, rows: 3, system: "paperpot" },
  { crops: ["koromač"], plantCm: 20, rowCm: 25, rows: 3, system: "paperpot" },
  { crops: ["shiso"], plantCm: 20, rowCm: 25, rows: 3, system: "paperpot" },
  { crops: ["bamija"], plantCm: 30, rowCm: 35, rows: 2, system: "paperpot", large: true },
  { crops: ["listni amarant"], plantCm: 15, rowCm: 20, rows: 4, system: "direct" },
  { crops: ["guar"], plantCm: 15, rowCm: 25, rows: 3, system: "paperpot" },
  { crops: ["salatni trpotec"], plantCm: 10, rowCm: 20, rows: 4, system: "direct" },
];

const BABY_LEAF_KEYWORDS = [
  "baby leaf", "rukola", "špinača", "blitva", "ohrovt", "mizuna", "mibuna",
  "tatsoi", "pak choi", "komatsuna", "gorčica", "kitajsko zelje", "rdeča pesa",
  "solatni trpotec", "cikorija", "endivija", "radič", "solata", "listni amarant",
  "palak", "methi", "shungiku",
];

function cropProfile(crop = {}, variety = {}) {
  const cropName = normalize(crop.name);
  const varietyName = normalize(variety.name);
  const isBabyCrop = normalize(crop.category) === "baby leaf" || cropName.includes("baby leaf");
  if (isBabyCrop) {
    return { plantCm: 2.5, rowCm: 6.4, rows: 6, system: "direct", babyCompatible: true, isBabyCrop: true };
  }

  const matched = CROP_PROFILES.find((profile) => includesAny(cropName, profile.crops));
  const profile = { ...DEFAULT_PROFILE, ...(matched || {}) };

  if (cropName === "solata" && varietyName.includes("lollo rosso")) profile.plantCm = 20;
  if (cropName === "koleraba" && varietyName.includes("superschmelz")) profile.plantCm = 30;
  if (cropName === "radič" && varietyName.includes("tržaški solatnik")) {
    Object.assign(profile, { plantCm: 5, rowCm: 15, rows: 5, system: "direct" });
  }
  if (cropName.includes("pak choi") && varietyName.includes("mei qing")) profile.plantCm = 15;
  if (cropName === "rdeča pesa" && varietyName.includes("cylindra")) profile.plantCm = 10;
  if (cropName === "rukola" && varietyName.includes("sylvetta")) profile.plantCm = 5;

  profile.babyCompatible = includesAny(cropName, BABY_LEAF_KEYWORDS);
  profile.isBabyCrop = false;
  return profile;
}

function paperpotSetup(targetCm) {
  const chains = [
    { cm: 5.08, label: "2″ (LP303-5)" },
    { cm: 10.16, label: "4″ (LP303-10)" },
    { cm: 15.24, label: "6″ (LP303-15)" },
  ];
  const options = chains.flatMap((chain) => Array.from({ length: 8 }, (_, index) => {
    const every = index + 1;
    return { ...chain, every, actualCm: chain.cm * every };
  }));
  options.sort((left, right) => (
    Math.abs(left.actualCm - targetCm) - Math.abs(right.actualCm - targetCm)
    || left.every - right.every
    || right.cm - left.cm
  ));
  const best = options[0];
  const actualCm = roundOne(best.actualCm);
  const localizedCm = String(actualCm).replace(".", ",");
  return {
    actualCm,
    setup: best.every === 1
      ? `Paperpot veriga ${best.label}; posej vsak lonček.`
      : `Paperpot veriga ${best.label}; posej vsak ${best.every}. lonček (${localizedCm} cm).`,
  };
}

function sixRowSetting(targetCm) {
  const settings = [
    { cm: 2.5, inches: "1″", setup: "notranji jermenici" },
    { cm: 6.4, inches: "2,5″", setup: "srednji jermenici" },
    { cm: 10.2, inches: "4″", setup: "zunanji jermenici" },
  ];
  return settings.reduce((best, item) => (
    Math.abs(item.cm - targetCm) < Math.abs(best.cm - targetCm) ? item : best
  ), settings[0]);
}

export function getGredicnikSpacing(crop = {}, variety = {}, mode = "standard") {
  const base = cropProfile(crop, variety);
  const cropLabel = [crop.name, variety.name].filter(Boolean).join(" · ") || "izbrano sorto";
  const isBabyMode = mode.startsWith("baby");
  const fixedRows = mode.endsWith("12") ? 12 : mode.endsWith("6") ? 6 : base.rows;

  if (isBabyMode) {
    return {
      mode,
      plantSpacingCm: 2.5,
      finalSpacingCm: 2.5,
      rowSpacingCm: 6.4,
      rows: fixedRows,
      equipment: "6 Row Seeder v2",
      equipmentShort: "6 Row v2",
      setup: "Nastavitev 1″: jermen na notranjih jermenicah; pred setvijo naredi kratek preizkus odmerjanja.",
      note: base.babyCompatible
        ? `Gostota je namenjena pridelavi ${cropLabel} kot baby leaf.`
        : `${cropLabel} se praviloma ne prideluje kot baby leaf; ta način uporabi le po lastnem preizkusu.`,
      suitable: base.babyCompatible,
      recommended: base.isBabyCrop && mode === "baby6",
    };
  }

  if (base.system === "manual") {
    return {
      mode,
      plantSpacingCm: base.plantCm,
      finalSpacingCm: base.plantCm,
      rowSpacingCm: base.rowCm,
      rows: fixedRows,
      equipment: "Ročno sajenje",
      equipmentShort: "Ročno",
      setup: "Ta pridelek ni primeren za Jang JP-1, 6-vrstno sejalnico ali običajno Paperpot verigo.",
      note: mode === "standard"
        ? "Uporabi navedeni končni razmik in ga prilagodi bujnosti sorte."
        : "Razpored 6 ali 12 vrst za ta pridelek praviloma ni primeren.",
      suitable: mode === "standard",
      recommended: mode === "standard",
    };
  }

  if (base.system === "paperpot") {
    const paperpot = paperpotSetup(base.plantCm);
    return {
      mode,
      plantSpacingCm: paperpot.actualCm,
      finalSpacingCm: paperpot.actualCm,
      rowSpacingCm: base.rowCm,
      rows: fixedRows,
      equipment: "Paperpot",
      equipmentShort: "Paperpot",
      setup: paperpot.setup,
      note: base.large
        ? "Večja sadika lahko preraste majhno Paperpot celico; presadi jo mlado ali uporabi večji plato in ročno sajenje."
        : "Razmik je prilagojen dejanskemu koraku Paperpot verige; po potrebi sejejo le izbrani lončki.",
      suitable: mode !== "seeder12" || base.plantCm <= 15,
      recommended: mode === "standard",
    };
  }

  if (mode === "standard") {
    return {
      mode,
      plantSpacingCm: base.plantCm,
      finalSpacingCm: base.plantCm,
      rowSpacingCm: base.rowCm,
      rows: base.rows,
      equipment: "Jang JP-1",
      equipmentShort: "Jang JP-1",
      setup: `Ciljaj na ${String(base.plantCm).replace(".", ",")} cm; valjček izberi po velikosti konkretnega semena, nato zobnike preveri po tabeli na sejalnici.`,
      note: "Pred setvijo naredi nekaj metrov preizkusa, ker velikost semena, valjček in drsenje kolesa vplivajo na dejanski razmik.",
      suitable: true,
      recommended: !base.isBabyCrop,
    };
  }

  const setting = sixRowSetting(base.plantCm);
  const needsThinning = base.plantCm > setting.cm + 0.2;
  return {
    mode,
    plantSpacingCm: setting.cm,
    finalSpacingCm: base.plantCm,
    rowSpacingCm: 6.4,
    rows: fixedRows,
    equipment: "6 Row Seeder v2",
    equipmentShort: "6 Row v2",
    setup: `Nastavitev ${setting.inches}: ${setting.setup}.${mode === "seeder12" ? " Za 12 vrst naredi dva vzporedna prehoda." : ""}`,
    note: needsThinning
      ? `Sej na ${String(setting.cm).replace(".", ",")} cm in po vzniku redči na končnih ${String(base.plantCm).replace(".", ",")} cm.`
      : "Izbrana nastavitev je najbližja standardnemu razmiku te kulture.",
    suitable: base.plantCm <= 20,
    recommended: false,
  };
}

export function getGredicnikSpacingOptions(crop = {}, variety = {}) {
  return Object.fromEntries(
    GREDICNIK_MODES.map(({ value }) => [value, getGredicnikSpacing(crop, variety, value)]),
  );
}
