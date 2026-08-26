import { apiRequest } from "./platform";

const css = `
.gm-backup-launch{position:fixed;left:18px;bottom:18px;z-index:9000;border:1px solid #143c2f;background:#fff;color:#143c2f;border-radius:999px;padding:10px 14px;font-weight:800;box-shadow:0 8px 24px rgba(0,0,0,.14);cursor:pointer}
.gm-backup-backdrop{position:fixed;inset:0;z-index:9999;background:rgba(15,24,20,.5);display:flex;align-items:center;justify-content:center;padding:18px}.gm-backup-modal{width:min(720px,100%);max-height:86vh;overflow:auto;background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.28)}.gm-backup-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:20px 22px;border-bottom:1px solid #e8e5de}.gm-backup-head h3{margin:0 0 5px}.gm-backup-head p{margin:0;color:#666;font-size:13px}.gm-backup-close{border:0;background:transparent;font-size:24px;cursor:pointer}.gm-backup-toolbar{padding:14px 22px;display:flex;gap:8px;flex-wrap:wrap;border-bottom:1px solid #eee}.gm-backup-btn{border:1px solid #143c2f;background:#143c2f;color:#fff;border-radius:9px;padding:9px 12px;font-weight:800;cursor:pointer}.gm-backup-btn.secondary{background:#fff;color:#143c2f}.gm-backup-list{padding:8px 22px 20px}.gm-backup-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;padding:12px 0;border-bottom:1px solid #eee}.gm-backup-row strong{display:block}.gm-backup-row small{color:#777}.gm-backup-empty{padding:24px 0;color:#777}.gm-backup-danger{border-color:#9a2f2f!important;color:#9a2f2f!important}
`;
document.head.insertAdjacentHTML("beforeend", `<style>${css}</style>`);

const fmtBytes = (value) => {
  const n = Number(value || 0);
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
};

async function loadList(list) {
  list.innerHTML = "<p class='gm-backup-empty'>Nalagam …</p>";
  const data = await apiRequest("/api/system/backups");
  list.innerHTML = "";
  if (!data.backups?.length) {
    list.innerHTML = "<p class='gm-backup-empty'>Varnostnih kopij še ni.</p>";
    return;
  }
  data.backups.forEach((backup) => {
    const row = document.createElement("div");
    row.className = "gm-backup-row";
    row.innerHTML = `<div><strong></strong><small></small></div><button class="gm-backup-btn secondary gm-backup-danger">OBNOVI</button>`;
    row.querySelector("strong").textContent = backup.name;
    row.querySelector("small").textContent = `${new Date(backup.created_at).toLocaleString()} · ${fmtBytes(backup.size_bytes)}`;
    row.querySelector("button").addEventListener("click", async () => {
      const confirm = prompt(`Obnova bo prepisala trenutno stanje. Pred obnovo bo GrowMaster sam ustvaril safety backup.\n\nZa obnovitev ${backup.name} vpiši OBNOVI:`);
      if (confirm !== "OBNOVI") return;
      try {
        const result = await apiRequest("/api/system/backups/restore", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: backup.name, confirm }),
        });
        alert(`${result.message}\nSafety backup: ${result.safety_backup?.name || "ustvarjen"}`);
        location.reload();
      } catch (error) {
        alert(error?.message || "Obnova ni uspela.");
      }
    });
    list.appendChild(row);
  });
}

function openBackupCenter() {
  const backdrop = document.createElement("div");
  backdrop.className = "gm-backup-backdrop";
  backdrop.innerHTML = `<div class="gm-backup-modal"><div class="gm-backup-head"><div><h3>Backup Center</h3><p>Varnostna kopija vsebuje PostgreSQL podatke in lokalne GrowMaster/Plant DB datoteke.</p></div><button class="gm-backup-close">×</button></div><div class="gm-backup-toolbar"><button class="gm-backup-btn" data-create>USTVARI BACKUP</button><button class="gm-backup-btn secondary" data-refresh>OSVEŽI</button></div><div class="gm-backup-list"></div></div>`;
  document.body.appendChild(backdrop);
  const list = backdrop.querySelector(".gm-backup-list");
  const close = () => backdrop.remove();
  backdrop.querySelector(".gm-backup-close").addEventListener("click", close);
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
  backdrop.querySelector("[data-refresh]").addEventListener("click", () => loadList(list));
  backdrop.querySelector("[data-create]").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const label = prompt("Neobvezna oznaka backupa (npr. pred-sezono):", "") ?? null;
    if (label === null) return;
    button.disabled = true;
    button.textContent = "USTVARJAM …";
    try {
      const result = await apiRequest("/api/system/backups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label }),
      });
      alert(`Backup ustvarjen: ${result.backup.name}`);
      await loadList(list);
    } catch (error) {
      alert(error?.message || "Backup ni uspel.");
    } finally {
      button.disabled = false;
      button.textContent = "USTVARI BACKUP";
    }
  });
  loadList(list).catch((error) => { list.innerHTML = `<p class="gm-backup-empty">${error?.message || "Backupa ni mogoče naložiti."}</p>`; });
}

function install() {
  if (document.getElementById("gm-backup-launch")) return;
  const button = document.createElement("button");
  button.id = "gm-backup-launch";
  button.className = "gm-backup-launch";
  button.type = "button";
  button.textContent = "BACKUP";
  button.addEventListener("click", openBackupCenter);
  document.body.appendChild(button);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install);
else install();
