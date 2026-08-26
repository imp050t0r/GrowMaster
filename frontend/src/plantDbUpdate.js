import { apiRequest } from "./platform";

const css = `
.gm-plantdb-btn{border:1px solid #143c2f;background:#143c2f;color:#fff;border-radius:9px;padding:9px 12px;font-weight:800;cursor:pointer}.gm-plantdb-btn:disabled{opacity:.5;cursor:wait}.gm-plantdb-version{font-size:11px;color:#69665f;font-weight:700}
.gm-pdb-backdrop{position:fixed;inset:0;background:rgba(15,24,20,.5);display:flex;align-items:center;justify-content:center;z-index:9999;padding:18px}.gm-pdb-modal{background:#fff;border-radius:16px;max-width:760px;width:100%;max-height:86vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.28)}.gm-pdb-head{padding:20px 22px 12px;border-bottom:1px solid #e8e5de}.gm-pdb-head h3{margin:0 0 6px;font-size:20px}.gm-pdb-head p{margin:0;color:#666;font-size:13px;line-height:1.45}.gm-pdb-list{padding:12px 22px;overflow:auto}.gm-pdb-item{display:flex;gap:10px;align-items:flex-start;padding:10px 0;border-bottom:1px solid #f0eee8}.gm-pdb-item input{margin-top:3px}.gm-pdb-item strong{display:block}.gm-pdb-item small{display:block;color:#777;margin-top:2px}.gm-pdb-actions{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;padding:14px 22px;border-top:1px solid #e8e5de}.gm-pdb-secondary{border:1px solid #bbb;background:#fff;color:#333;border-radius:9px;padding:9px 12px;font-weight:800;cursor:pointer}.gm-pdb-note{padding:10px 22px;background:#f7f5ef;color:#4b4943;font-size:12px}
`;
document.head.insertAdjacentHTML("beforeend", `<style>${css}</style>`);

async function refreshLabel(button, label) {
  try {
    const data = await apiRequest("/api/system/plant-db");
    label.textContent = `Plant DB ${data.plant_db_version || "ni inicializirana"}`;
    try {
      const remote = await apiRequest("/api/system/plant-db/update-status");
      if (remote.update_available) {
        label.textContent += ` · na voljo ${remote.available_version}`;
        button.textContent = "PREVERI NOVOSTI V BAZI";
      }
    } catch { /* Lokalna baza ostane uporabna tudi brez interneta. */ }
  } catch {
    label.textContent = "Plant DB —";
  }
}

function closeDialog(dialog) {
  dialog?.remove();
}

function createDialog(preview, onApplied) {
  const backdrop = document.createElement("div");
  backdrop.className = "gm-pdb-backdrop";
  const modal = document.createElement("div");
  modal.className = "gm-pdb-modal";
  modal.innerHTML = `
    <div class="gm-pdb-head">
      <h3>Nova Plant DB ${preview.available_version || ""}</h3>
      <p>GrowMaster je našel ${preview.new_entry_count || 0} novih kultur/sort. Nič ne bo dodano brez tvoje potrditve.</p>
    </div>
    <div class="gm-pdb-note">Tvoje obstoječe nastavitve ostanejo nespremenjene. Dodajo se samo označene nove postavke.</div>
    <div class="gm-pdb-list"></div>
    <div class="gm-pdb-actions">
      <button class="gm-pdb-secondary" data-action="skip">PRESKOČI ZA ZDAJ</button>
      <button class="gm-pdb-secondary" data-action="all">OZNAČI VSE</button>
      <button class="gm-plantdb-btn" data-action="apply">DODAJ IZBRANE</button>
    </div>`;
  backdrop.appendChild(modal);
  document.body.appendChild(backdrop);

  const list = modal.querySelector(".gm-pdb-list");
  if (!preview.entries?.length) {
    list.innerHTML = `<p style="color:#666">Ni novih kultur ali sort za dodajanje.</p>`;
  } else {
    preview.entries.forEach((entry) => {
      const row = document.createElement("label");
      row.className = "gm-pdb-item";
      row.innerHTML = `<input type="checkbox" value=""><span><strong></strong><small></small></span>`;
      const input = row.querySelector("input");
      input.value = entry.key;
      row.querySelector("strong").textContent = entry.label;
      row.querySelector("small").textContent = entry.detail || entry.type;
      list.appendChild(row);
    });
  }

  modal.querySelector('[data-action="skip"]').addEventListener("click", () => closeDialog(backdrop));
  modal.querySelector('[data-action="all"]').addEventListener("click", () => {
    list.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = true; });
  });
  modal.querySelector('[data-action="apply"]').addEventListener("click", async (event) => {
    const selected = [...list.querySelectorAll('input[type="checkbox"]:checked')].map((input) => input.value);
    if (!selected.length) {
      alert("Izberi vsaj eno novo postavko ali uporabi »Preskoči za zdaj«.");
      return;
    }
    const apply = event.currentTarget;
    apply.disabled = true;
    apply.textContent = "DODAJAM …";
    try {
      const result = await apiRequest("/api/system/plant-db/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entries: selected }),
      });
      closeDialog(backdrop);
      alert(`Dodano: ${result.approved_entry_count || selected.length}. Preostalih neprevzetih: ${result.remaining_entry_count || 0}.`);
      window.dispatchEvent(new CustomEvent("growmaster:plant-db-updated", { detail: result }));
      onApplied?.(result);
    } catch (error) {
      alert(error?.message || "Izbranih postavk ni bilo mogoče dodati.");
      apply.disabled = false;
      apply.textContent = "DODAJ IZBRANE";
    }
  });
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeDialog(backdrop); });
}

function install() {
  const toolbar = document.querySelector(".gm-seed-toolbar");
  if (!toolbar || document.getElementById("gm-plantdb-reload")) return;
  const label = document.createElement("span");
  label.className = "gm-plantdb-version";
  const button = document.createElement("button");
  button.id = "gm-plantdb-reload";
  button.className = "gm-plantdb-btn";
  button.type = "button";
  button.textContent = "PREVERI BAZO PODATKOV";
  button.addEventListener("click", async () => {
    button.disabled = true;
    const old = button.textContent;
    button.textContent = "PREVERJAM …";
    try {
      const preview = await apiRequest("/api/system/plant-db/update-preview");
      createDialog(preview, () => refreshLabel(button, label));
      button.textContent = old;
    } catch (error) {
      button.textContent = "NAPAKA";
      alert(error?.message || "Plant DB ni bilo mogoče preveriti.");
      setTimeout(() => { button.textContent = old; }, 1800);
    } finally {
      button.disabled = false;
    }
  });
  toolbar.append(label, button);
  refreshLabel(button, label);
}

install();
new MutationObserver(install).observe(document.documentElement, { childList: true, subtree: true });
