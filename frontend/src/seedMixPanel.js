import { apiRequest } from "./platform";

export function initSeedMixPanel() {
  const state = { recipes: [], preview: null, selected: "", error: "", notice: "" };

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  }
  function n(value, digits = 2) {
    return Number(value || 0).toLocaleString("sl-SI", { maximumFractionDigits: digits });
  }
  function rateInputs(recipe) {
    return (recipe?.components || []).map((c) => `<label>${esc(c.crop)} – setvena norma g/m²<input data-mix-rate="${esc(c.crop)}" type="number" min="0.001" step="0.001" required value="${c.crop === "Baby leaf regrat" ? "0.65" : ""}"></label>`).join("");
  }
  function previewHtml(preview) {
    if (!preview) return "";
    const rows = preview.components.map((c) => {
      const status = c.enough_stock ? "OK" : (c.required_seed_g == null ? "MANJKA NORMA" : "NI DOVOLJ");
      const cls = c.enough_stock ? "gm-OK" : "gm-ORDER";
      const lots = (c.allocations || []).map((a) => `${esc(a.variety || "osnovna")}: ${n(a.take_g)} g`).join(" · ");
      return `<div class="gm-seed-row"><div><strong>${esc(c.crop)} · ${n(c.share_pct,0)} %</strong><small>${n(c.area_m2)} m² · potrebno ${c.required_seed_g == null ? "—" : `${n(c.required_seed_g)} g`} · na zalogi ${c.available_seed_g == null ? "—" : `${n(c.available_seed_g)} g`}${lots ? `<br>${lots}` : ""}</small></div><div class="gm-seed-status ${cls}">${status}</div></div>`;
    }).join("");
    const blockers = [
      ...(preview.missing_seed_rates || []).map((x) => `Manjka setvena norma: ${x}`),
      ...(preview.unmatched_inventory_components || []).map((x) => `Ni zaloge: ${x}`),
      ...(preview.shortages || []).map((x) => `Primanjkljaj ${x.crop}: ${n(x.shortage_g)} g`),
    ];
    return `${blockers.length ? `<div class="gm-seed-warn">${blockers.map(esc).join("<br>")}</div>` : `<div class="gm-seed-notice">Vse komponente imajo dovolj zaloge. Skupaj ${n(preview.total_seed_g)} g semena.</div>`}<div class="gm-seed-list">${rows}</div><div class="gm-seed-actions" style="margin-top:12px"><button id="gm-mix-consume" class="gm-seed-action" type="button" ${preview.inventory_ready ? "" : "disabled"}>POTRDI SETEV IN ODŠTEJ SEME</button></div>`;
  }

  async function loadRecipes() {
    const data = await apiRequest("/api/seed-inventory/mix-recipes");
    state.recipes = data.recipes || [];
    if (!state.selected && state.recipes.length) state.selected = state.recipes[0].id;
  }

  async function preview(form) {
    const fd = new FormData(form);
    const rates = {};
    form.querySelectorAll("[data-mix-rate]").forEach((el) => { rates[el.dataset.mixRate] = Number(el.value); });
    const body = {
      width_m: Number(fd.get("width_m")),
      length_m: Number(fd.get("length_m")),
      reserve_pct: Number(fd.get("reserve_pct")),
      reference: String(fd.get("reference") || "").trim() || null,
      seed_rates_g_m2: rates,
    };
    state.preview = await apiRequest(`/api/seed-inventory/mix-recipes/${encodeURIComponent(state.selected)}/inventory-preview`, { method: "POST", body: JSON.stringify(body) });
    state.preview._request = body;
  }

  async function consume() {
    if (!state.preview?.inventory_ready || !state.preview?._request) return;
    const result = await apiRequest(`/api/seed-inventory/mix-recipes/${encodeURIComponent(state.selected)}/consume`, { method: "POST", body: JSON.stringify(state.preview._request) });
    state.notice = result.message || "Semena so odšteta iz zaloge.";
    state.preview = null;
  }

  function mount(container) {
    if (!container) return;
    const recipe = state.recipes.find((r) => r.id === state.selected);
    container.innerHTML = `${state.notice ? `<div class="gm-seed-notice">${esc(state.notice)}</div>` : ""}${state.error ? `<div class="gm-seed-error">${esc(state.error)}</div>` : ""}<form id="gm-mix-form" class="gm-seed-form"><h3>Baby leaf mešanica</h3><label>Receptura<select id="gm-mix-recipe">${state.recipes.map((r) => `<option value="${esc(r.id)}" ${r.id === state.selected ? "selected" : ""}>${esc(r.name)}</option>`).join("")}</select></label><label>Širina gredice (m)<input name="width_m" type="number" value="0.8" min="0.1" step="0.1" required></label><label>Dolžina gredice (m)<input name="length_m" type="number" value="15" min="0.1" step="0.1" required></label><label>Rezerva semena (%)<input name="reserve_pct" type="number" value="5" min="0" max="100" step="1"></label><label style="grid-column:1/-1">Referenca setve<input name="reference" placeholder="npr. Gredica B12 / 2026-08-27"></label><h3>Sestava in setvene norme</h3>${rateInputs(recipe)}<button type="submit">PREVERI ZALOGO</button></form>${recipe ? `<div class="gm-seed-warn"><strong>${esc(recipe.name)}</strong><br>${recipe.components.map((c) => `${esc(c.crop)} ${n(c.share_pct,0)} %`).join(" · ")}<br><small>${esc(recipe.note || "")}</small></div>` : ""}${previewHtml(state.preview)}`;
    const form = container.querySelector("#gm-mix-form");
    form?.addEventListener("submit", async (e) => { e.preventDefault(); state.error = ""; state.notice = ""; try { await preview(form); mount(container); } catch (err) { state.error = err.message || String(err); mount(container); } });
    container.querySelector("#gm-mix-recipe")?.addEventListener("change", (e) => { state.selected = e.target.value; state.preview = null; mount(container); });
    container.querySelector("#gm-mix-consume")?.addEventListener("click", async () => { if (!confirm("Potrdi setev in odštej vse komponente mešanice iz Seed Inventory?")) return; state.error = ""; try { await consume(); mount(container); } catch (err) { state.error = err.message || String(err); mount(container); } });
  }

  return { loadRecipes, mount };
}
