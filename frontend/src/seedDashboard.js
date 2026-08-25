import { apiRequest } from "./platform";

const STYLE_ID = "gm-seed-dashboard-style";
const CARD_ID = "gm-seed-dashboard-card";
let loading = false;
let lastLoadedAt = 0;

if (!document.getElementById(STYLE_ID)) {
  document.head.insertAdjacentHTML("beforeend", `<style id="${STYLE_ID}">
  #${CARD_ID}{margin-bottom:18px;border:1px solid #d9d4c8;background:linear-gradient(135deg,#f7f4ec,#fff);border-radius:18px;padding:18px;box-shadow:0 8px 24px #143c2f0d}
  .gm-seed-dash-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:12px}.gm-seed-dash-head h2{margin:2px 0 4px}.gm-seed-dash-head p{margin:0;color:#6a675f}.gm-seed-dash-kicker{font-size:11px;font-weight:900;letter-spacing:.09em;text-transform:uppercase;color:#617268}
  .gm-seed-dash-actions{display:flex;gap:8px;flex-wrap:wrap}.gm-seed-dash-button{border:0;border-radius:9px;padding:9px 12px;font-weight:800;cursor:pointer;background:#143c2f;color:#fff}.gm-seed-dash-button.secondary{background:#e8e3d8;color:#143c2f}
  .gm-seed-dash-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:12px 0}.gm-seed-dash-metric{background:#fff;border:1px solid #e3dfd5;border-radius:12px;padding:10px}.gm-seed-dash-metric span{display:block;font-size:12px;color:#6b6861}.gm-seed-dash-metric strong{display:block;margin-top:2px;font-size:23px;color:#143c2f}.gm-seed-dash-metric.order strong{color:#a53024}.gm-seed-dash-metric.low strong{color:#9a6a00}
  .gm-seed-dash-list{display:grid;gap:7px}.gm-seed-dash-row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;background:#fff;border:1px solid #e3dfd5;border-radius:11px;padding:10px 12px}.gm-seed-dash-date{font-weight:900;color:#143c2f;min-width:52px}.gm-seed-dash-main strong{display:block}.gm-seed-dash-main small{display:block;color:#6b6861;margin-top:2px}.gm-seed-dash-status{font-size:12px;font-weight:900;white-space:nowrap}.gm-seed-dash-status.ORDER{color:#a53024}.gm-seed-dash-status.LOW_STOCK{color:#9a6a00}.gm-seed-dash-status.OK{color:#17633c}.gm-seed-dash-empty{background:#fff;border:1px dashed #d6d0c5;border-radius:12px;padding:18px;color:#666;text-align:center}.gm-seed-dash-warning{margin-top:8px;padding:9px 11px;border-radius:10px;background:#fff0ce;color:#705000;font-size:13px}
  @media(max-width:760px){.gm-seed-dash-head{display:grid}.gm-seed-dash-actions{justify-content:flex-start}.gm-seed-dash-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.gm-seed-dash-row{grid-template-columns:auto 1fr}.gm-seed-dash-status{grid-column:2}.gm-seed-dash-metric strong{font-size:20px}}
  </style>`);
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
}

function n(value, digits = 1) {
  return Number(value || 0).toLocaleString("sl-SI", { maximumFractionDigits: digits });
}

function shortDate(value) {
  if (!value) return "—";
  const parts = String(value).split("-");
  return parts.length === 3 ? `${Number(parts[2])}.${Number(parts[1])}.` : value;
}

function label(status) {
  return ({ ORDER: "NAROČI", LOW_STOCK: "NIZKA ZALOGA", OK: "PRIPRAVLJENO" }[status] || status || "—");
}

function flattenPlans(data) {
  const rows = [];
  for (const item of data.items || []) {
    for (const plan of item.plans || []) {
      rows.push({
        ...plan,
        crop: item.crop,
        variety: item.variety,
        status: item.status,
        available_quantity: item.available_quantity,
        remaining_after_plan: item.remaining_after_plan,
      });
    }
  }
  return rows.sort((a, b) => String(a.sowing_date).localeCompare(String(b.sowing_date)) || String(a.bed).localeCompare(String(b.bed)));
}

function renderCard(card, data) {
  const summary = data.summary || {};
  const plans = flattenPlans(data);
  const warnings = data.warnings || [];
  card.innerHTML = `
    <div class="gm-seed-dash-head">
      <div><span class="gm-seed-dash-kicker">Naslednjih 14 dni</span><h2>🌱 Seme za prihajajoče setve</h2><p>${plans.length ? `${plans.length} planiranih setev · preverjena zaloga in rezervacije` : "Trenutno ni planiranih setev, ki bi potrebovale seme."}</p></div>
      <div class="gm-seed-dash-actions"><button type="button" class="gm-seed-dash-button secondary" data-gm-seed-refresh>OSVEŽI</button><button type="button" class="gm-seed-dash-button" data-gm-seed-open>ODPRI SEED CENTER</button></div>
    </div>
    <div class="gm-seed-dash-metrics">
      <div class="gm-seed-dash-metric"><span>Planirane setve</span><strong>${Number(data.planned_sowings || plans.length)}</strong></div>
      <div class="gm-seed-dash-metric"><span>Pripravljeno</span><strong>${Number(summary.ok || 0)}</strong></div>
      <div class="gm-seed-dash-metric low"><span>Nizka zaloga</span><strong>${Number(summary.low_stock || 0)}</strong></div>
      <div class="gm-seed-dash-metric order"><span>Za naročiti</span><strong>${Number(summary.order || 0)}</strong></div>
    </div>
    ${plans.length ? `<div class="gm-seed-dash-list">${plans.slice(0, 6).map((plan) => `<div class="gm-seed-dash-row"><div class="gm-seed-dash-date">${esc(shortDate(plan.sowing_date))}</div><div class="gm-seed-dash-main"><strong>${esc(plan.crop)} · ${esc(plan.variety)}</strong><small>Gredica ${esc(plan.bed)} · ${n(plan.required_quantity, 2)} ${esc(plan.unit)} potrebno</small></div><div class="gm-seed-dash-status ${esc(plan.status)}">${esc(label(plan.status))}</div></div>`).join("")}</div>` : `<div class="gm-seed-dash-empty">V naslednjih 14 dneh ni planiranih setev z izračunano potrebo po semenu.</div>`}
    ${plans.length > 6 ? `<div class="gm-seed-dash-warning">Še ${plans.length - 6} setev je prikazanih v Seed Centerju.</div>` : ""}
    ${warnings.length ? `<div class="gm-seed-dash-warning">⚠ ${warnings.length} planiranih setev nima dovolj podatkov za zanesljiv izračun količine semena.</div>` : ""}
  `;
  card.querySelector("[data-gm-seed-open]")?.addEventListener("click", () => window.GrowMasterSeedCenter?.open?.("forecast"));
  card.querySelector("[data-gm-seed-refresh]")?.addEventListener("click", () => refreshDashboard(true));
}

function dashboardAnchor() {
  return document.querySelector(".smart-review-panel");
}

async function refreshDashboard(force = false) {
  const anchor = dashboardAnchor();
  if (!anchor || loading) return;
  if (!force && Date.now() - lastLoadedAt < 60_000 && document.getElementById(CARD_ID)) return;
  loading = true;
  let card = document.getElementById(CARD_ID);
  if (!card) {
    card = document.createElement("section");
    card.id = CARD_ID;
    card.className = "panel";
    anchor.parentElement?.insertBefore(card, anchor);
  }
  card.innerHTML = `<div class="gm-seed-dash-empty">Preverjam seme za naslednjih 14 dni …</div>`;
  try {
    const data = await apiRequest("/api/seed-inventory/forecast?horizon_days=14");
    renderCard(card, data);
    lastLoadedAt = Date.now();
  } catch (error) {
    card.innerHTML = `<div class="gm-seed-dash-warning">Seed pregled trenutno ni na voljo: ${esc(error.message || "napaka pri povezavi")}</div>`;
  } finally {
    loading = false;
  }
}

function syncDashboardCard() {
  const anchor = dashboardAnchor();
  const card = document.getElementById(CARD_ID);
  if (!anchor) {
    card?.remove();
    return;
  }
  refreshDashboard(false);
}

const observer = new MutationObserver(syncDashboardCard);
observer.observe(document.getElementById("root") || document.body, { childList: true, subtree: true });
window.setTimeout(syncDashboardCard, 900);
window.addEventListener("focus", () => refreshDashboard(false));
window.addEventListener("growmaster:seed-changed", () => refreshDashboard(true));
