import test from "node:test";
import assert from "node:assert/strict";

import { GREDICNIK_MODES, getGredicnikSpacing, getGredicnikSpacingOptions } from "./gredicnikSpacing.js";

test("Jang JP-1 and Six Row v2 profiles follow the selected layout", () => {
  const crop = { name: "Korenje", category: "Domača" };
  const variety = { name: "Nantes" };
  const standard = getGredicnikSpacing(crop, variety, "standard");
  const sixRows = getGredicnikSpacing(crop, variety, "seeder6");
  const tenRows = getGredicnikSpacing(crop, variety, "seeder10");
  const legacyTwelveRows = getGredicnikSpacing(crop, variety, "seeder12");

  assert.equal(standard.equipment, "Jang JP-1");
  assert.equal(standard.plantSpacingCm, 2.5);
  assert.equal(sixRows.equipment, "6 Row Seeder v2");
  assert.equal(sixRows.rowSpacingCm, 6.4);
  assert.equal(sixRows.rows, 6);
  assert.equal(tenRows.rows, 10);
  assert.equal(tenRows.edgeMarginCm, 11.2);
  assert.equal(tenRows.layoutFits, true);
  assert.match(tenRows.setup, /dva prilagojena prehoda po pet/);
  assert.equal(legacyTwelveRows.mode, "seeder10");
  assert.equal(legacyTwelveRows.rows, 10);
});

test("Paperpot recommendation selects a real chain step", () => {
  const lettuce = getGredicnikSpacing(
    { name: "Solata", category: "Domača" },
    { name: "Ljubljanska ledenka" },
    "standard",
  );
  assert.equal(lettuce.equipment, "Paperpot");
  assert.equal(lettuce.plantSpacingCm, 25.4);
  assert.match(lettuce.setup, /LP303-5/);
  assert.match(lettuce.setup, /vsak 5\. lonček/);

  const oakleaf = getGredicnikSpacing(
    { name: "Solata", category: "Domača" },
    { name: "Panisse", seed_spacing_cm: 20.3, row_spacing_cm: 25 },
    "standard",
  );
  assert.equal(oakleaf.equipment, "Paperpot");
  assert.equal(oakleaf.plantSpacingCm, 20.3);
  assert.equal(oakleaf.rowSpacingCm, 25);
  assert.equal(oakleaf.rows, 3);
  assert.equal(oakleaf.edgeMarginCm, 15);
  assert.match(oakleaf.setup, /vsak 2\. lonček/);
});

test("variety overrides and baby leaf suitability are retained", () => {
  const compactKohlrabi = getGredicnikSpacing(
    { name: "Koleraba", category: "Domača" },
    { name: "Dunajska bela" },
    "standard",
  );
  const largeKohlrabi = getGredicnikSpacing(
    { name: "Koleraba", category: "Domača" },
    { name: "Superschmelz" },
    "standard",
  );
  assert.equal(compactKohlrabi.plantSpacingCm, 15.2);
  assert.equal(largeKohlrabi.plantSpacingCm, 30.5);

  const babyOptions = getGredicnikSpacingOptions(
    { name: "Baby leaf mizuna", category: "Baby leaf" },
    { name: "Green" },
  );
  assert.equal(babyOptions.baby6.suitable, true);
  assert.equal(babyOptions.baby6.recommended, true);
  assert.equal(babyOptions.baby10.recommended, false);
  assert.equal(babyOptions.baby10.plantSpacingCm, 2.5);
  assert.equal(babyOptions.baby10.edgeMarginCm, 11.2);

  const tomatoBaby = getGredicnikSpacing(
    { name: "Paradižnik", category: "Domača" },
    { name: "Val" },
    "baby6",
  );
  assert.equal(tomatoBaby.suitable, false);

  const oakleafBaby = getGredicnikSpacing(
    { name: "Solata", category: "Domača" },
    { name: "Green Saladbowl" },
    "baby10",
  );
  assert.equal(oakleafBaby.suitable, true);
  assert.equal(oakleafBaby.rows, 10);
});

test("80 cm bed keeps a safe edge margin and rejects layouts that are too wide", () => {
  const babyTen = getGredicnikSpacing(
    { name: "Baby leaf mizuna", category: "Baby leaf" },
    { name: "Green" },
    "baby10",
  );
  assert.equal(babyTen.rows, 10);
  assert.equal(babyTen.rowSpacingCm, 6.4);
  assert.equal(babyTen.edgeMarginCm, 11.2);
  assert.equal(babyTen.suitable, true);

  const lettuceSix = getGredicnikSpacing(
    { name: "Solata", category: "Domača" },
    { name: "Ljubljanska ledenka" },
    "seeder6",
  );
  assert.equal(lettuceSix.layoutFits, false);
  assert.equal(lettuceSix.suitable, false);
  assert.match(lettuceSix.geometryNote, /najmanj 8 cm/);
});

test("supplier metadata refines standard spacing without changing fixed seeder layouts", () => {
  const crop = { name: "Rukola", category: "Domača" };
  const astro = {
    name: "Astro",
    seed_spacing_cm: 0.5,
    row_spacing_cm: 5.1,
  };
  const standard = getGredicnikSpacing(crop, astro, "standard");
  const tenRows = getGredicnikSpacing(crop, astro, "seeder10");

  assert.equal(standard.plantSpacingCm, 0.5);
  assert.equal(standard.rowSpacingCm, 5.1);
  assert.equal(tenRows.rows, 10);
  assert.equal(tenRows.rowSpacingCm, 6.4);
  assert.equal(tenRows.edgeMarginCm, 11.2);
});

test("every catalog crop receives values for all five layouts", () => {
  const catalogCrops = [
    "Rukola", "Solata", "Paradižnik", "Paprika", "Feferon", "Jajčevec", "Kumara", "Bučka", "Buča",
    "Fižol", "Grah", "Bob", "Korenje", "Rdeča pesa", "Redkvica", "Čebula", "Por", "Česen", "Zelje",
    "Cvetača", "Brokoli", "Koleraba", "Repa", "Špinača", "Blitva", "Endivija", "Motovilec", "Radič",
    "Krompir", "Peteršilj", "Zelena", "Koromač", "Mizuna", "Pak Choi", "Tatsoi", "Komatsuna", "Choi Sum",
    "Kailan", "Daikon", "Pekinško zelje", "Mibuna", "Japonska repa", "Azijska gorčica", "Shiso", "Shungiku",
    "Edamame", "Methi", "Bamija", "Karela", "Lauki", "Rebrasta bučka", "Gobasta bučka", "Tinda",
    "Voščena buča", "Indijski jajčevec", "Indijski čili", "Nepalski zeleni čili", "Malabarska špinača", "Listni amarant", "Palak",
    "Guar", "Koriander", "Baby leaf mešanica", "Divja rukola", "Salatni trpotec", "Cikorija",
    "Mladi listi rdeče pese", "Baby leaf špinača", "Baby leaf ohrovt", "Baby leaf listna solata",
    "Baby leaf hrastov list", "Baby leaf rimska solata", "Baby leaf batavia", "Baby leaf endivija",
    "Baby leaf radič", "Baby leaf blitva", "Baby leaf gorčica", "Baby leaf mizuna", "Baby leaf tatsoi",
    "Baby leaf pak choi", "Baby leaf komatsuna", "Baby leaf kitajsko zelje",
  ];

  for (const cropName of catalogCrops) {
    const category = cropName.startsWith("Baby leaf") || cropName === "Mladi listi rdeče pese" ? "Baby leaf" : "Domača";
    const options = getGredicnikSpacingOptions({ name: cropName, category }, { name: "Standardna sorta" });
    assert.deepEqual(Object.keys(options), GREDICNIK_MODES.map(({ value }) => value));
    for (const option of Object.values(options)) {
      assert.ok(option.plantSpacingCm > 0, cropName);
      assert.ok(option.rowSpacingCm > 0, cropName);
      assert.ok(option.rows > 0, cropName);
      assert.ok(option.equipment, cropName);
      assert.ok(option.setup, cropName);
    }
  }
});
