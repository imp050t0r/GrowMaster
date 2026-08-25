import { apiRequest } from "./platform";

const css = `
.gm-plantdb-btn{border:1px solid #143c2f;background:#143c2f;color:#fff;border-radius:9px;padding:9px 12px;font-weight:800;cursor:pointer}.gm-plantdb-btn:disabled{opacity:.5;cursor:wait}.gm-plantdb-version{font-size:11px;color:#69665f;font-weight:700}
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
        button.textContent = "PRENESI POSODOBITEV BAZE";
      }
    } catch { /* Lokalna baza ostane uporabna tudi brez interneta. */ }
  } catch {
    label.textContent = "Plant DB —";
  }
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
  button.textContent = "POSODOBI BAZO PODATKOV";
  button.addEventListener("click", async () => {
    button.disabled = true;
    const old = button.textContent;
    button.textContent = "NALAGAM …";
    try {
      const result = await apiRequest("/api/system/plant-db/update", { method: "POST" });
      button.textContent = "POSODOBLJENO ✓";
      label.textContent = `Plant DB ${result.plant_db_version || "aktivna"}`;
      window.dispatchEvent(new CustomEvent("growmaster:plant-db-updated", { detail: result }));
      setTimeout(() => { button.textContent = old; }, 1800);
    } catch (error) {
      button.textContent = "NAPAKA";
      alert(error?.message || "Plant DB ni bilo mogoče ponovno naložiti.");
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
