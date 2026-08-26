import { apiFetch, apiRequest } from "./platform";

const css = `
.gm-backup-launch{position:fixed;left:18px;bottom:18px;z-index:9000;border:1px solid #143c2f;background:#fff;color:#143c2f;border-radius:999px;padding:10px 14px;font-weight:800;box-shadow:0 8px 24px rgba(0,0,0,.14);cursor:pointer}
.gm-backup-backdrop{position:fixed;inset:0;z-index:9999;background:rgba(15,24,20,.5);display:flex;align-items:center;justify-content:center;padding:18px}.gm-backup-modal{width:min(760px,100%);max-height:86vh;overflow:auto;background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.28)}.gm-backup-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:20px 22px;border-bottom:1px solid #e8e5de}.gm-backup-head h3{margin:0 0 5px}.gm-backup-head p{margin:0;color:#666;font-size:13px}.gm-backup-close{border:0;background:transparent;font-size:24px;cursor:pointer}.gm-backup-toolbar{padding:14px 22px;display:flex;gap:8px;flex-wrap:wrap;border-bottom:1px solid #eee}.gm-backup-btn{border:1px solid #143c2f;background:#143c2f;color:#fff;border-radius:9px;padding:9px 12px;font-weight:800;cursor:pointer}.gm-backup-btn.secondary{background:#fff;color:#143c2f}.gm-backup-list{padding:8px 22px 20px}.gm-backup-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;padding:12px 0;border-bottom:1px solid #eee}.gm-backup-actions{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}.gm-backup-row strong{display:block}.gm-backup-row small{color:#777}.gm-backup-empty{padding:24px 0;color:#777}.gm-backup-danger{border-color:#9a2f2f!important;color:#9a2f2f!important}.gm-backup-owner{padding:10px 22px;background:#f7f5ef;color:#555;font-size:12px;border-bottom:1px solid #eee}
`;
document.head.insertAdjacentHTML("beforeend", `<style>${css}</style>`);

const fmtBytes = (value) => {
  const n = Number(value || 0);
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
};

async function backupBlob(name) {
  const response = await apiFetch(`/api/system/backups/${encodeURIComponent(name)}/download`);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "Backupa ni mogoče izvoziti.");
  }
  return response.blob();
}

async function saveBackupFile(name) {
  const blob = await backupBlob(name);

  // Desktop Chromium/Edge: this is a real system Save As picker, so the user
  // explicitly chooses the disk/folder instead of GrowMaster guessing a path.
  if (window.showSaveFilePicker) {
    const handle = await window.showSaveFilePicker({
      suggestedName: name,
      types: [{ description: "GrowMaster backup", accept: { "application/octet-stream": [".gmbak", ".zip"] } }],
    });
    const writable = await handle.createWritable();
    await writable.write(blob);
    await writable.close();
    return "saved";
  }

  // Android/iOS: prefer the native share/save sheet when the WebView supports files.
  const file = new File([blob], name, { type: "application/octet-stream" });
  if (navigator.canShare?.({ files: [file] })) {
    await navigator.share({ files: [file], title: "GrowMaster backup" });
    return "shared";
  }

  // Fallback for browsers without the File System Access API. Depending on browser
  // settings this opens Save As or stores the file in the configured Downloads folder.
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
  return "downloaded";
}

async function loadList(list, ownerLabel) {
  list.innerHTML = "<p class='gm-backup-empty'>Nalagam …</p>";
  const data = await apiRequest("/api/system/backups");
  if (ownerLabel) ownerLabel.textContent = `Tvoja ločena backup mapa · ID namestitve: ${data.owner_id || "—"}`;
  list.innerHTML = "";
  if (!data.backups?.length) {
    list.innerHTML = "<p class='gm-backup-empty'>Varnostnih kopij še ni.</p>";
    return;
  }
  data.backups.forEach((backup) => {
    const row = document.createElement("div");
    row.className = "gm-backup-row";
    row.innerHTML = `<div><strong></strong><small></small></div><div class="gm-backup-actions"><button class="gm-backup-btn secondary" data-save>SHRANI KOT …</button><button class="gm-backup-btn secondary gm-backup-danger" data-restore>OBNOVI</button></div>`;
    row.querySelector("strong").textContent = backup.name;
    row.querySelector("small").textContent = `${new Date(backup.created_at).toLocaleString()} · ${fmtBytes(backup.size_bytes)}`;
    row.querySelector("[data-save]").addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        await saveBackupFile(backup.name);
      } catch (error) {
        if (error?.name !== "AbortError") alert(error?.message || "Backupa ni bilo mogoče shraniti.");
      } finally {
        button.disabled = false;
      }
    });
    row.querySelector("[data-restore]").addEventListener("click", async () => {
      const confirm = prompt(`Obnova bo prepisala trenutno stanje. Pred obnovo bo GrowMaster sam ustvaril safety backup v tvoji ločeni mapi.\n\nZa obnovitev ${backup.name} vpiši OBNOVI:`);
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
  backdrop.innerHTML = `<div class="gm-backup-modal"><div class="gm-backup-head"><div><h3>Backup Center</h3><p>Vsaka namestitev GrowMasterja ima svojo ločeno backup mapo. Po izdelavi te GrowMaster vpraša, kam želiš shraniti dodatno kopijo.</p></div><button class="gm-backup-close">×</button></div><div class="gm-backup-owner"></div><div class="gm-backup-toolbar"><button class="gm-backup-btn" data-create>USTVARI BACKUP</button><button class="gm-backup-btn secondary" data-refresh>OSVEŽI</button></div><div class="gm-backup-list"></div></div>`;
  document.body.appendChild(backdrop);
  const list = backdrop.querySelector(".gm-backup-list");
  const ownerLabel = backdrop.querySelector(".gm-backup-owner");
  const close = () => backdrop.remove();
  backdrop.querySelector(".gm-backup-close").addEventListener("click", close);
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
  backdrop.querySelector("[data-refresh]").addEventListener("click", () => loadList(list, ownerLabel));
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
      await loadList(list, ownerLabel);
      try {
        await saveBackupFile(result.backup.name);
      } catch (error) {
        if (error?.name !== "AbortError") {
          alert(`Interni backup je varno ustvarjen, zunanje kopije pa ni bilo mogoče shraniti: ${error?.message || "napaka"}`);
        }
      }
    } catch (error) {
      alert(error?.message || "Backup ni uspel.");
    } finally {
      button.disabled = false;
      button.textContent = "USTVARI BACKUP";
    }
  });
  loadList(list, ownerLabel).catch((error) => { list.innerHTML = `<p class="gm-backup-empty">${error?.message || "Backupa ni mogoče naložiti."}</p>`; });
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
