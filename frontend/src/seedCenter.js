import { apiRequest } from "./platform";

const state = {
  open: false,
  tab: "forecast",
  data: {},
  plantings: [],
  loading: false,
  error: "",
  notice: "",
  filter: "",
};

const tabs = [
  ["forecast", "Napoved"],
  ["inventory", "Zaloga"],
  ["reservations", "Rezervirano"],
  ["orders", "Naročila"],
  ["quality", "Podatki"],
  ["learning", "Učenje"],
];

const css = `
#gm-seed-button{position:fixed;right:18px;bottom:82px;z-index:1190;border:0;border-radius:999px;background:#143c2f;color:#fff;padding:12px 17px;font-weight:800;box-shadow:0 8px 28px #0003;cursor:pointer;transition:.18s transform,.18s box-shadow}
#gm-seed-button:hover{transform:translateY(-2px);box-shadow:0 11px 30px #0004}
#gm-seed-center{position:fixed;inset:0;z-index:1300;background:#07110dcc;display:none;align-items:stretch;justify-content:flex-end;backdrop-filter:blur(3px)}
#gm-seed-center.gm-seed-open{display:flex}
.gm-seed-shell{width:min(920px,100%);height:100%;overflow:auto;background:#f7f4ec;padding:22px;box-shadow:-12px 0 42px #0005}
.gm-seed-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;position:sticky;top:-22px;background:#f7f4ec;z-index:5;padding:22px 0 12px}
.gm-seed-head h2{margin:2px 0 2px;color:#143c2f;font-size:28px}.gm-seed-head p{margin:0;color:#69665f;font-size:13px}.gm-seed-close{font-size:28px;line-height:1;border:0;background:transparent;cursor:pointer;padding:5px 8px;border-radius:8px}.gm-seed-close:hover{background:#e8e3d8}
.gm-seed-toolbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin:6px 0 14px}.gm-seed-filter{flex:1;min-width:180px;padding:9px 11px;border:1px solid #c8c3b7;border-radius:9px;background:#fff}.gm-seed-refresh{border:1px solid #c8c3b7;background:#fff;color:#143c2f;border-radius:9px;padding:9px 12px;font-weight:800;cursor:pointer}
.gm-seed-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 16px}.gm-seed-tabs button{border:1px solid #c9c4b7;border-radius:999px;background:#fff;padding:8px 12px;cursor:pointer;font-weight:700}.gm-seed-tabs button.active{background:#143c2f;color:#fff;border-color:#143c2f}
.gm-seed-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:10px;margin:12px 0 16px}.gm-seed-card,.gm-seed-row{background:#fff;border:1px solid #ded9cd;border-radius:14px;padding:13px}.gm-seed-card strong{font-size:24px;display:block;color:#143c2f}.gm-seed-list{display:grid;gap:9px}.gm-seed-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center}.gm-seed-row strong{overflow-wrap:anywhere}.gm-seed-row small{color:#69665f;display:block;margin-top:3px;line-height:1.35}.gm-seed-status{font-weight:900;white-space:nowrap}.gm-ORDER{color:#a53024}.gm-LOW_STOCK{color:#9a6a00}.gm-OK{color:#17633c}
.gm-seed-progress{height:6px;background:#eee9df;border-radius:999px;margin-top:7px;overflow:hidden}.gm-seed-progress>span{display:block;height:100%;background:#143c2f;border-radius:999px}
.gm-seed-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;background:#fff;padding:14px;border-radius:14px;border:1px solid #ded9cd;margin-bottom:14px}.gm-seed-form h3{grid-column:1/-1;margin:0 0 2px;color:#143c2f}.gm-seed-form label{display:grid;gap:4px;font-size:12px;font-weight:700}.gm-seed-form input,.gm-seed-form select{padding:9px;border:1px solid #c8c3b7;border-radius:8px;background:#fff;min-width:0}.gm-seed-form button,.gm-seed-action{padding:9px 11px;border:0;border-radius:9px;background:#143c2f;color:#fff;font-weight:800;cursor:pointer}.gm-seed-form>button{grid-column:1/-1}.gm-seed-action.secondary{background:#e7e2d6;color:#143c2f}.gm-seed-action:disabled{opacity:.45;cursor:not-allowed}.gm-seed-actions{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;align-items:center}.gm-seed-warn,.gm-seed-error,.gm-seed-notice{padding:10px 12px;border-radius:10px;margin:0 0 12px}.gm-seed-warn{background:#fff0ce;color:#705000}.gm-seed-error{background:#ffe1dc;color:#8c2b20}.gm-seed-notice{background:#dff3e6;color:#195d38}.gm-seed-empty{text-align:center;padding:28px 16px;color:#69665f;background:#fff;border:1px dashed #cfc9bd;border-radius:14px}.gm-seed-kicker{font-size:11px;text-transform:uppercase;letter-spacing:.09em;font-weight:900;color:#6b7a72}.gm-seed-section-title{display:flex;justify-content:space-between;align-items:end;gap:10px;margin:18px 0 8px}.gm-seed-section-title h3{margin:0;color:#143c2f}.gm-seed-section-title small{color:#69665f}
.gm-seed-nav-entry{display:flex!important;align-items:center;gap:8px;width:100%;cursor:pointer}.gm-seed-nav-badge{min-width:20px;height:20px;padding:0 6px;display:inline-flex;align-items:center;justify-content:center;border-radius:999px;background:#a53024;color:#fff;font-size:11px;font-weight:900}
@media(max-width:650px){.gm-seed-shell{padding:14px}.gm-seed-head{top:-14px;padding:14px 0 10px}.gm-seed-form{grid-template-columns:1fr}.gm-seed-row{grid-template-columns:1fr}.gm-seed-actions{justify-content:flex-start}#gm-seed-button{bottom:72px;right:12px}.gm-seed-head h2{font-size:24px}}
`;

document.head.insertAdjacentHTML("beforeend", `<style>${css}</style>`);
document.body.insertAdjacentHTML("beforeend", `
  <button id="gm-seed-button" type="button" aria-label="Odpri Seed Center">🌱 Seme</button>
  <aside id="gm-seed-center" role="dialog" aria-modal="true" aria-label="Seed Center">
    <div class="gm-seed-shell">
      <div class="gm-seed-head">
        <div><span class="gm-seed-kicker">GrowMaster operativa</span><h2>Seed Center</h2><p>Od plana in zaloge do naročila, setve in učenja.</p></div>
        <button class="gm-seed-close" aria-label="Zapri">×</button>
      </div>
      <div class="gm-seed-toolbar"><input class="gm-seed-filter" type="search" placeholder="Filtriraj kulturo, sorto, lot ali dobavitelja …"><button class="gm-seed-refresh" type="button">OBNOVI</button></div>
      <div class="gm-seed-tabs"></div>
      <div id="gm-seed-content"></div>
    </div>
  </aside>`);

const root = document.getElementById("gm-seed-center");
const content = document.getElementById("gm-seed-content");
const filterInput = document.querySelector(".gm-seed-filter");

function esc(value) { return String(value ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m])); }
function n(value, digits = 1) { return Number(value || 0).toLocaleString("sl-SI", { maximumFractionDigits: digits }); }
function statusLabel(value) { return ({ ORDER: "NAROČI", LOW_STOCK: "NIZKA ZALOGA", OK: "OK" }[value] || value || "—"); }
function matches(item) { const q = state.filter.trim().toLocaleLowerCase("sl"); if (!q) return true; return JSON.stringify(item).toLocaleLowerCase("sl").includes(q); }
function filtered(items) { return (items || []).filter(matches); }
function metrics(values) { return `<div class="gm-seed-metrics">${values.map(([label, value, cls = ""]) => `<div class="gm-seed-card"><small>${esc(label)}</small><strong class="${cls}">${esc(value)}</strong></div>`).join("")}</div>`; }
function rows(items, builder) { const list = filtered(items); return list.length ? `<div class="gm-seed-list">${list.map(builder).join("")}</div>` : `<div class="gm-seed-empty">Za trenutni filter ni zapisov.</div>`; }
function notice() { return `${state.notice ? `<div class="gm-seed-notice">${esc(state.notice)}</div>` : ""}${state.error ? `<div class="gm-seed-error">${esc(state.error)}</div>` : ""}`; }
function pct(value) { return Math.max(0, Math.min(100, Number(value || 0))); }

function drawTabs() {
  document.querySelector(".gm-seed-tabs").innerHTML = tabs.map(([key, label]) => `<button type="button" data-tab="${key}" class="${state.tab === key ? "active" : ""}">${label}</button>`).join("");
}

function plantingOptions() {
  return state.plantings.map((p) => `<option value="${p.id}">${esc(`${p.crop} ${p.variety} · ${p.bed} · ${p.sowing_date}`)}</option>`).join("");
}

function render() {
  drawTabs();
  if (state.loading) { content.innerHTML = `${notice()}<div class="gm-seed-card">Nalagam podatke …</div>`; return; }
  const d = state.data || {};

  if (state.tab === "forecast") {
    const s = d.summary || {};
    content.innerHTML = notice() + metrics([["OK", s.ok || 0, "gm-OK"], ["Nizka zaloga", s.low_stock || 0, "gm-LOW_STOCK"], ["Naroči", s.order || 0, "gm-ORDER"], ["Brez norme", s.missing_seed_rate || 0]]) + rows(d.items, (i) => {
      const coverage = i.required_quantity > 0 ? pct((i.available_quantity / i.required_quantity) * 100) : 100;
      return `<div class="gm-seed-row"><div><strong>${esc(i.crop)} · ${esc(i.variety)}</strong><small>${n(i.required_quantity, 2)} ${esc(i.unit)} potrebno · ${n(i.available_quantity, 2)} na zalogi · po planu ${n(i.remaining_after_plan, 2)}</small><div class="gm-seed-progress"><span style="width:${coverage}%"></span></div></div><div class="gm-seed-status gm-${i.status}">${statusLabel(i.status)}</div></div>`;
    });
  } else if (state.tab === "inventory") {
    content.innerHTML = notice() + `<form id="gm-seed-add" class="gm-seed-form"><h3>Nova semenska serija</h3><label>Kultura<input name="crop" required></label><label>Sorta<input name="variety"></label><label>Enota<select name="unit"><option value="g">g</option><option value="seeds">semena</option><option value="pellets">peleti</option></select></label><label>Količina<input name="quantity" type="number" min="0" step="0.01" required></label><label>Velikost paketa<input name="package_size" type="number" min="0" step="0.01"></label><label>TKW/TSW g/1000<input name="thousand_seed_weight_g" type="number" min="0" step="0.001"></label><label>Kalivost %<input name="germination_pct" type="number" value="95" min="1" max="100"></label><label>Vznik %<input name="field_emergence_pct" type="number" value="90" min="1" max="100"></label><label>Dobavitelj<input name="supplier"></label><label>Lot<input name="lot_number"></label><button>SHRANI SERIJO</button></form>` + metrics([["Aktivne serije", d.lot_count || 0]]) + rows(d.lots, (i) => `<div class="gm-seed-row"><div><strong>${esc(i.crop)} ${esc(i.variety || "")}</strong><small>${esc(i.supplier || "brez dobavitelja")} · lot ${esc(i.lot_number || "—")} · kalivost ${n(i.germination_pct, 0)} %</small></div><div><strong>${n(i.quantity, 2)} ${esc(i.unit)}</strong><small>${i.package_size ? `paket ${n(i.package_size, 2)}` : ""}</small></div></div>`);
  } else if (state.tab === "reservations") {
    const s = d.summary || {};
    content.innerHTML = notice() + metrics([["Proste", s.ok || 0, "gm-OK"], ["Nizke", s.low_stock || 0, "gm-LOW_STOCK"], ["Primanjkljaj", s.order || 0, "gm-ORDER"], ["Planirane setve", d.planned_sowings || 0]]) + rows(d.items, (i) => `<div class="gm-seed-row"><div><strong>${esc(i.crop)} · ${esc(i.variety)}</strong><small>fizično ${n(i.physical_quantity, 2)} · rezervirano ${n(i.reserved_quantity, 2)} · prosto ${n(i.free_quantity, 2)} ${esc(i.unit)}</small></div><div class="gm-seed-status gm-${i.status}">${statusLabel(i.status)}</div></div>`);
  } else if (state.tab === "orders") {
    content.innerHTML = notice() + metrics([["Predlogi naročil", d.count || 0]]) + `<p class="gm-seed-warn">Naročilo se ustvari v obstoječem modulu Nabava. Za oddajo mora biti povezan dobavitelj in znana cena.</p>` + rows(d.drafts, (i, index) => `<div class="gm-seed-row"><div><strong>${esc(i.crop)} · ${esc(i.variety)}</strong><small>${i.packages_to_order || "?"} paketov · ${n(i.order_quantity, 2)} ${esc(i.unit)} · ${esc(i.supplier_hint || "dobavitelj ni povezan")}</small></div><div class="gm-seed-actions">${i.supplier_id && i.order_quantity ? `<button class="gm-seed-action" type="button" data-create-order="${index}">USTVARI NAROČILO</button>` : `<span class="gm-seed-status gm-LOW_STOCK">DOPOLNI PODATKE</span>`}</div></div>`);
  } else if (state.tab === "quality") {
    const s = d.summary || {};
    content.innerHTML = notice() + `<div class="gm-seed-actions"><button class="gm-seed-action secondary" type="button" id="gm-backfill-preview">PREVERI DOPOLNITVE</button><button class="gm-seed-action" type="button" id="gm-backfill-apply">DOPOLNI PREVERJENE NORME</button></div>` + metrics([["Popolni", s.complete || 0, "gm-OK"], ["Delni", s.partial || 0, "gm-LOW_STOCK"], ["Nepopolni", s.incomplete || 0, "gm-ORDER"]]) + rows(d.items, (i) => `<div class="gm-seed-row"><div><strong>${esc(i.crop)} · ${esc(i.variety)}</strong><small>manjka: ${esc((i.missing || []).join(", ") || "nič")}</small><div class="gm-seed-progress"><span style="width:${pct(i.score)}%"></span></div></div><div><strong>${i.score}%</strong></div></div>`);
  } else {
    content.innerHTML = notice() + metrics([["Predlogi za učenje", d.count || 0]]) + `<form id="gm-actual-use" class="gm-seed-form"><h3>Dejanska poraba pri setvi</h3><label>Setev<select name="planting_id" required><option value="">Izberi setev …</option>${plantingOptions()}</select></label><label>Dejanska poraba<input name="quantity" type="number" min="0.01" step="0.01" required></label><label>Enota<select name="unit"><option value="g">g</option><option value="seeds">semena</option><option value="pellets">peleti</option></select></label><label>Opomba<input name="note" placeholder="npr. kalibracija, ostanek v hopperju"></label><button>ZAPIŠI DEJANSKO PORABO</button></form><p class="gm-seed-warn">GrowMaster se setvene norme uči samo iz dejansko zapisane porabe. DTM in pridelek temeljita na dejanskih žetvah.</p>` + rows(d.suggestions, (i, index) => `<div class="gm-seed-row"><div><strong>${esc(i.crop)} · ${esc(i.variety)}</strong><small>${i.samples} ciklov · ${i.seed_use_samples || 0} z dejansko porabo · DTM ${i.current_days_to_harvest} → ${i.observed_days_to_harvest ?? "—"} · norma ${i.current_seed_rate_g_m2 ?? "—"} → ${i.observed_seed_rate_g_m2 ?? "—"} g/m²</small></div><div class="gm-seed-actions">${i.recommend_seed_rate_update ? `<button class="gm-seed-action" type="button" data-apply-rate="${index}">UPORABI NORMO</button>` : ""}${i.recommend_dtm_review ? `<button class="gm-seed-action secondary" type="button" data-apply-dtm="${index}">UPORABI DTM</button>` : ""}<strong>${esc(i.confidence)}</strong></div></div>`);
  }
}

const paths = {
  forecast: "/api/seed-inventory/forecast",
  inventory: "/api/seed-inventory",
  reservations: "/api/seed-inventory/reservations",
  orders: "/api/seed-inventory/purchase-drafts",
  quality: "/api/master-data/quality",
  learning: "/api/agronomy/learning",
};

async function load() {
  state.loading = true; state.error = ""; render();
  try {
    const requests = [apiRequest(paths[state.tab])];
    if (state.tab === "learning" && state.plantings.length === 0) requests.push(apiRequest("/api/plantings"));
    const [data, plantings] = await Promise.all(requests);
    state.data = data;
    if (plantings) state.plantings = plantings;
  } catch (error) { state.error = error.message || "Seed Center ni dosegljiv."; }
  finally { state.loading = false; render(); }
}

async function post(path, body) { return apiRequest(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }); }
function done(message) { state.notice = message; state.error = ""; load(); }
function fail(error) { state.error = error.message || "Zahteva ni uspela."; render(); }

function openSeedCenter(tab = state.tab) { state.tab = tab; state.notice = ""; root.classList.add("gm-seed-open"); state.open = true; filterInput.focus(); load(); }
function closeSeedCenter() { root.classList.remove("gm-seed-open"); state.open = false; }

function injectNavigationEntry() {
  if (document.querySelector("[data-gm-seed-nav]")) return;
  const candidates = [...document.querySelectorAll("button")];
  const purchasing = candidates.find((button) => button.textContent?.includes("Nabava"));
  if (!purchasing?.parentElement) return;
  const button = purchasing.cloneNode(true);
  button.removeAttribute("class");
  button.className = purchasing.className;
  button.dataset.gmSeedNav = "1";
  button.type = "button";
  button.innerHTML = `<span>🌱</span><span>Seme</span>`;
  button.addEventListener("click", () => openSeedCenter("forecast"));
  purchasing.parentElement.insertBefore(button, purchasing.nextSibling);
  document.getElementById("gm-seed-button").style.display = "none";
}

const navObserver = new MutationObserver(() => injectNavigationEntry());
navObserver.observe(document.body, { childList: true, subtree: true });
window.setTimeout(injectNavigationEntry, 500);

// Lightweight badge: order shortages appear next to the menu/floating entry when available.
async function refreshBadge() {
  try {
    const forecast = await apiRequest("/api/seed-inventory/forecast");
    const count = Number(forecast.summary?.order || 0);
    const nav = document.querySelector("[data-gm-seed-nav]");
    if (nav) {
      nav.querySelector(".gm-seed-nav-badge")?.remove();
      if (count > 0) nav.insertAdjacentHTML("beforeend", `<span class="gm-seed-nav-badge" title="Potrebno naročilo semena">${count}</span>`);
    }
  } catch { /* login/API may not be ready yet */ }
}
window.setTimeout(refreshBadge, 1600);
window.addEventListener("focus", refreshBadge);

document.getElementById("gm-seed-button").addEventListener("click", () => openSeedCenter("forecast"));
document.querySelector(".gm-seed-close").addEventListener("click", closeSeedCenter);
root.addEventListener("click", (event) => { if (event.target === root) closeSeedCenter(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && state.open) closeSeedCenter(); });
document.querySelector(".gm-seed-refresh").addEventListener("click", load);
filterInput.addEventListener("input", (event) => { state.filter = event.target.value; render(); });
document.querySelector(".gm-seed-tabs").addEventListener("click", (event) => { const button = event.target.closest("[data-tab]"); if (!button) return; state.notice = ""; state.error = ""; state.tab = button.dataset.tab; load(); });

content.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    if (event.target.id === "gm-seed-add") {
      const form = new FormData(event.target); const body = Object.fromEntries(form.entries());
      for (const key of ["quantity", "package_size", "thousand_seed_weight_g", "germination_pct", "field_emergence_pct"]) body[key] = body[key] ? Number(body[key]) : null;
      await post("/api/seed-inventory/lots", body); done("Semenska serija je dodana.");
    } else if (event.target.id === "gm-actual-use") {
      const form = new FormData(event.target); const plantingId = Number(form.get("planting_id"));
      await post(`/api/seed-inventory/plantings/${plantingId}/actual-seed-use`, { quantity: Number(form.get("quantity")), unit: form.get("unit"), note: form.get("note") || null });
      done("Dejanska poraba je zapisana in je na voljo učnemu sistemu.");
    }
  } catch (error) { fail(error); }
});

content.addEventListener("click", async (event) => {
  try {
    const orderButton = event.target.closest("[data-create-order]");
    if (orderButton) {
      const draft = filtered(state.data.drafts)[Number(orderButton.dataset.createOrder)];
      if (!draft) return;
      const price = Number(window.prompt(`Cena na ${draft.unit} za ${draft.crop} ${draft.variety}:`, "0"));
      if (!price || price <= 0) return;
      await post("/api/seed-inventory/purchase-orders", { supplier_id: draft.supplier_id, crop: draft.crop, variety: draft.variety, quantity: draft.order_quantity, unit: draft.unit, unit_price_eur: price });
      done("Nabavno naročilo je ustvarjeno v modulu Nabava."); refreshBadge(); return;
    }
    if (event.target.id === "gm-backfill-preview") {
      const result = await apiRequest("/api/master-data/backfill-seeding?dry_run=true", { method: "POST" });
      state.notice = `Preverjeno: možnih dopolnitev ${result.change_count}. Noben podatek še ni bil spremenjen.`; render(); return;
    }
    if (event.target.id === "gm-backfill-apply") {
      if (!window.confirm("Zapišem samo eksplicitno konfigurirane setvene norme v master podatke?")) return;
      const result = await apiRequest("/api/master-data/backfill-seeding?dry_run=false", { method: "POST" });
      done(`Dopolnjenih norm: ${result.change_count}.`); return;
    }
    const rateButton = event.target.closest("[data-apply-rate]");
    const dtmButton = event.target.closest("[data-apply-dtm]");
    const button = rateButton || dtmButton;
    if (button) {
      const suggestion = filtered(state.data.suggestions)[Number(button.dataset.applyRate ?? button.dataset.applyDtm)];
      if (!suggestion) return;
      const useRate = Boolean(rateButton); const field = useRate ? "seed_rate_g_m2" : "days_to_harvest";
      const value = useRate ? suggestion.observed_seed_rate_g_m2 : suggestion.observed_days_to_harvest;
      if (value == null) return;
      if (!window.confirm(`Potrdim ${suggestion.crop} ${suggestion.variety}: ${field} = ${value}?`)) return;
      await post("/api/agronomy/learning/apply", { crop: suggestion.crop, variety: suggestion.variety, field, value, confirmation: "APPLY" });
      done("Naučena vrednost je potrjena in zapisana v master podatke.");
    }
  } catch (error) { fail(error); }
});

window.GrowMasterSeedCenter = { open: openSeedCenter, refresh: load };
