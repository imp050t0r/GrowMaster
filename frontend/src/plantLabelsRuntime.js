const exactTypeByVariety = new Map([
  ["green saladbowl", "Hrastov list zelen"],
  ["salad bowl", "Hrastov list zelen"],
  ["oaking", "Hrastov list zelen"],
  ["piro", "Hrastov list zelen"],
  ["panisse", "Hrastov list zelen"],
  ["green oakleaf", "Hrastov list zelen"],
  ["red saladbowl", "Hrastov list rdeč"],
  ["red salad bowl", "Hrastov list rdeč"],
  ["digitale", "Hrastov list rdeč"],
  ["oscarde", "Hrastov list rdeč"],
  ["red oakleaf", "Hrastov list rdeč"],
]);

const norm = (value) => String(value || "").trim().toLocaleLowerCase("sl");

function display(crop, variety) {
  const cropName = String(crop || "").trim() || "Neznana kultura";
  const varietyName = String(variety || "").trim();
  return {
    primary: exactTypeByVariety.get(norm(varietyName)) || cropName,
    secondary: varietyName || null,
  };
}

let inventoryLots = [];
let inventoryLoading = false;

async function ensureInventoryLots() {
  if (inventoryLots.length || inventoryLoading) return;
  inventoryLoading = true;
  try {
    const response = await fetch("/api/seed-inventory", { credentials: "include" });
    if (response.ok) {
      const data = await response.json();
      inventoryLots = Array.isArray(data?.lots) ? data.lots : [];
    }
  } catch {
    // Login/API may not be ready yet. Mutation observer will retry later.
  } finally {
    inventoryLoading = false;
  }
}

function setPrimarySecondary(strong, crop, variety) {
  if (!strong || strong.dataset.gmPlantLabel === "1") return;
  const d = display(crop, variety);
  strong.textContent = d.primary;
  strong.dataset.gmPlantLabel = "1";
  if (d.secondary) {
    const existing = strong.parentElement?.querySelector(":scope > .gm-plant-variety");
    if (!existing) {
      const small = document.createElement("small");
      small.className = "gm-plant-variety";
      small.textContent = `Sorta: ${d.secondary}`;
      strong.insertAdjacentElement("afterend", small);
    }
  }
}

function processStrong(strong) {
  if (!strong || strong.dataset.gmPlantLabel === "1") return;
  const text = strong.textContent?.trim() || "";
  if (!text) return;

  if (text.includes(" · ")) {
    const [crop, ...rest] = text.split(" · ");
    const variety = rest.join(" · ").trim();
    if (crop && variety) setPrimarySecondary(strong, crop, variety);
    return;
  }

  for (const lot of inventoryLots) {
    const full = `${lot.crop || ""} ${lot.variety || ""}`.trim();
    if (full && text === full) {
      setPrimarySecondary(strong, lot.crop, lot.variety);
      return;
    }
  }
}

async function processSeedCenter() {
  const rows = [...document.querySelectorAll("#gm-seed-center .gm-seed-row > div:first-child > strong")];
  if (!rows.length) return;
  await ensureInventoryLots();
  rows.forEach(processStrong);
}

const observer = new MutationObserver(() => { processSeedCenter(); });
observer.observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("focus", () => { inventoryLots = []; processSeedCenter(); });
window.setTimeout(processSeedCenter, 700);

window.GrowMasterPlantDisplay = { display };
