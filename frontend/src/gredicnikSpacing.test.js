import test from "node:test";
import assert from "node:assert/strict";

import { GREDICNIK_MODES, getGredicnikSpacing, getGredicnikSpacingOptions } from "./gredicnikSpacing.js";

test("Jang JP-1 and Six Row v2 profiles follow the selected layout", () => {
  const crop = { name: "Korenje", category: "Domača" };
  const variety = { name: "Nantes" };
  const standard = getGredicnikSpacing(crop, variety, "standard");
  const sixRows = getGredicnikSpacing(crop, variety, "seeder6");
  const twelveRows = getGredicnikSpacing(crop, variety, "seeder12");

  assert.equal(standard.equipment, "Jang JP-1");
  assert.equal(standard.plantSpacingCm, 2.5);
  assert.equal(sixRows.equipment, "6 Row Seeder v2");
  assert.equal(sixRows.rowSpacingCm, 6.4);
  assert.equal(sixRows.rows, 6);
  assert.equal(twelveRows.rows, 12);
  assert.match(twelveRows.setup, /dva vzporedna prehoda/);
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
  assert.equal(babyOptions.baby12.recommended, false);
  assert.equal(babyOptions.baby12.plantSpacingCm, 2.5);

  const tomatoBaby = getGredicnikSpacing(
    { name: "Paradižnik", category: "Domača" },
    { name: "Val" },
    "baby6",
  );
  assert.equal(tomatoBaby.suitable, false);
});

test("every catalog crop receives values for all five layouts", () => {
  const catalogCrops = [
    "Rukola", "Solata", "Paradižnik", "Paprika", "Feferon", "Jajčevec", "Kumara", "Bučka", "Buča",
    "Fižol", "Grah", "Bob", "Korenje", "Rdeča pesa", "Redkvica", "Čebula", "Por", "Česen", "Zelje",
    "Cvetača", "Brokoli", "Koleraba", "Repa", "Špinača", "Blitva", "Endivija", "Motovilec", "Radič",
    "Krompir", "Peteršilj", "Zelena", "Koromač", "Mizuna", "Pak Choi", "Tatsoi", "Komatsuna", "Choi Sum",
    "Kailan", "Daikon", "Pekinško zelje", "Mibuna", "Japonska repa", "Azijska gorčica", "Shiso", "Shungiku",
    "Edamame", "Methi", "Bamija", "Karela", "Lauki", "Rebrasta bučka", "Gobasta bučka", "Tinda",
    "Voščena buča", "Indijski jajčevec", "Indijski čili", "Malabarska špinača", "Listni amarant", "Palak",
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
