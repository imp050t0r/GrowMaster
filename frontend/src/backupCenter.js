import { apiFetch } from "./platform";

const css = `
.gm-backup-launch{position:fixed;left:18px;bottom:18px;z-index:9000;border:1px solid #143c2f;background:#fff;color:#143c2f;border-radius:999px;padding:10px 14px;font-weight:800;box-shadow:0 8px 24px rgba(0,0,0,.14);cursor:pointer}
.gm-backup-backdrop{position:fixed;inset:0;z-index:9999;background:rgba(15,24,20,.5);display:flex;align-items:center;justify-content:center;padding:18px}.gm-backup-modal{width:min(720px,100%);background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.28)}.gm-backup-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:20px 22px;border-bottom:1px solid #e8e5de}.gm-backup-head h3{margin:0 0 5px}.gm-backup-head p{margin:0;color:#666;font-size:13px;line-height:1.45}.gm-backup-close{border:0;background:transparent;font-size:24px;cursor:pointer}.gm-backup-body{padding:22px}.gm-backup-actions{display:flex;gap:10px;flex-wrap:wrap}.gm-backup-btn{border:1px solid #143c2f;background:#143c2f;color:#fff;border-radius:9px;padding:11px 15px;font-weight:800;cursor:pointer}.gm-backup-btn.secondary{background:#fff;color:#143c2f}.gm-backup-btn.danger{background:#8a2525;border-color:#8a2525}.gm-backup-btn:disabled{opacity:.55;cursor:default}.gm-backup-note{margin:14px 0 0;color:#666;font-size:13px;line-height:1.5}.gm-backup-status{margin-top:16px;padding:12px 14px;border-radius:10px;background:#f7f5ef;color:#333;font-size:13px;line-height:1.45}.gm-backup-status[data-kind="error"]{background:#fff1f1;color:#8a2525}.gm-backup-status[data-kind="success"]{background:#eef8f1;color:#1f6638}.gm-restore-confirm{margin-top:16px;padding:16px;border:1px solid #ead8d8;border-radius:12px;background:#fffafa;line-height:1.45}.gm-restore-confirm strong{display:block;margin-bottom:8px}.gm-restore-file{font-family:monospace;overflow-wrap:anywhere}.gm-restore-meta{margin-top:8px;color:#555;font-size:13px}.gm-restore-confirm input{width:100%;box-sizing:border-box;margin:12px 0;padding:10px;border:1px solid #bbb;border-radius:8px}
`;
document.head.insertAdjacentHTML("beforeend", `<style>${css}</style>`);

function suggestedBackupName() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  const stamp = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}_${pad(now.getHours())}-${pad(now.getMinutes())}`;
  return `GrowMaster-backup-${stamp}.json`;
}

async function responseError(response, fallback) {
  const data = await response.json().catch(() => ({}));
  return new Error(data.detail || fallback);
}

async function fetchBackupBlob() {
  const response = await apiFetch("/api/system/backups/export");
  if (!response.ok) throw await responseError(response, "Backupa ni bilo mogoče ustvariti.");
  return response.blob();
}

async function saveWithDesktopPicker(handle) {
  const blob = await fetchBackupBlob();
  const writable = await handle.createWritable();
  await writable.write(blob);
  await writable.close();
}

async function fallbackDownload() {
  const blob = await fetchBackupBlob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = suggestedBackupName();
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

async function chooseRestoreFile() {
  if (window.showOpenFilePicker) {
    const [handle] = await window.showOpenFilePicker({
      multiple: false,
      types: [{ description: "GrowMaster varnostna kopija", accept: { "application/json": [".json"] } }],
    });
    return handle.getFile();
  }
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json,application/json";
    input.style.display = "none";
    document.body.appendChild(input);
    input.addEventListener("change", () => {
      const file = input.files?.[0] || null;
      input.remove();
      resolve(file);
    }, { once: true });
    input.click();
  });
}

async function readBackupSummary(file) {
  if (!file.name.toLowerCase().endsWith(".json")) throw new Error("Izberi GrowMaster .json backup datoteko.");
  if (file.size > 25 * 1024 * 1024) throw new Error("Backup je večji od dovoljenih 25 MB.");
  let documentData;
  try { documentData = JSON.parse(await file.text()); }
  catch { throw new Error("Datoteka ni veljaven JSON backup."); }
  const payload = documentData?.payload;
  if (payload?.format !== "growmaster-portable-backup" || !documentData?.checksum_sha256) {
    throw new Error("Datoteka ni prepoznana kot GrowMaster backup.");
  }
  return {
    createdAt: payload.created_at || "neznano",
    records: Number.isFinite(payload.record_count) ? payload.record_count : "neznano",
  };
}

async function restoreFile(file) {
  const response = await apiFetch("/api/system/backups/restore?confirmation=OBNOVI", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: file,
  });
  if (!response.ok) throw await responseError(response, "Obnova ni uspela.");
  return response.json();
}

function setStatus(status, message, kind = "") {
  status.hidden = false;
  status.dataset.kind = kind;
  status.textContent = message;
}

function openBackupCenter() {
  const backdrop = document.createElement("div");
  backdrop.className = "gm-backup-backdrop";
  backdrop.innerHTML = `<div class="gm-backup-modal"><div class="gm-backup-head"><div><h3>Backup Center</h3><p>Backup in restore iz datoteke, ki jo sam izbereš.</p></div><button class="gm-backup-close" type="button">×</button></div><div class="gm-backup-body"><div class="gm-backup-actions"><button class="gm-backup-btn" type="button" data-create>IZBERI MESTO IN SHRANI BACKUP</button><button class="gm-backup-btn secondary" type="button" data-restore>OBNOVI IZ BACKUPA</button></div><p class="gm-backup-note">Pri backupu z miško izbereš disk, mapo in ime datoteke. Pri obnovi izbereš .json backup na kateremkoli disku ali USB ključu. Pred obnovo GrowMaster samodejno shrani trenutno stanje.</p><div class="gm-backup-status" hidden aria-live="polite"></div><div class="gm-restore-confirm" hidden><strong>Potrdi obnovitev</strong><div>Datoteka: <span class="gm-restore-file" data-file-name></span></div><div class="gm-restore-meta" data-file-meta></div><div style="margin-top:10px">Obnova bo zamenjala trenutne poslovne podatke. Za nadaljevanje vpiši <b>OBNOVI</b>.</div><input data-confirm-input autocomplete="off" placeholder="OBNOVI"><button class="gm-backup-btn danger" type="button" data-confirm-restore disabled>OBNOVI PODATKE</button></div></div></div>`;
  document.body.appendChild(backdrop);

  const createButton = backdrop.querySelector("[data-create]");
  const restoreButton = backdrop.querySelector("[data-restore]");
  const status = backdrop.querySelector(".gm-backup-status");
  const confirmBox = backdrop.querySelector(".gm-restore-confirm");
  const confirmInput = backdrop.querySelector("[data-confirm-input]");
  const confirmButton = backdrop.querySelector("[data-confirm-restore]");
  const fileName = backdrop.querySelector("[data-file-name]");
  const fileMeta = backdrop.querySelector("[data-file-meta]");
  let selectedFile = null;

  const close = () => backdrop.remove();
  backdrop.querySelector(".gm-backup-close").addEventListener("click", close);
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) close(); });

  createButton.addEventListener("click", async () => {
    createButton.disabled = true;
    status.hidden = true;
    try {
      if (window.showSaveFilePicker) {
        const handle = await window.showSaveFilePicker({
          suggestedName: suggestedBackupName(),
          types: [{ description: "GrowMaster varnostna kopija", accept: { "application/json": [".json"] } }],
        });
        setStatus(status, "Ustvarjam backup in ga zapisujem na izbrano mesto …");
        await saveWithDesktopPicker(handle);
        setStatus(status, `Backup je shranjen kot »${handle.name}«.`, "success");
      } else {
        await fallbackDownload();
        setStatus(status, "Backup je ustvarjen. Če sistem vpraša za mesto, izberi disk, mapo in ime datoteke.", "success");
      }
    } catch (error) {
      if (error?.name === "AbortError") setStatus(status, "Shranjevanje je preklicano.");
      else setStatus(status, error?.message || "Backup ni uspel.", "error");
    } finally { createButton.disabled = false; }
  });

  restoreButton.addEventListener("click", async () => {
    status.hidden = true;
    confirmBox.hidden = true;
    confirmInput.value = "";
    confirmButton.disabled = true;
    selectedFile = null;
    try {
      const file = await chooseRestoreFile();
      if (!file) return;
      const summary = await readBackupSummary(file);
      selectedFile = file;
      fileName.textContent = file.name;
      const created = summary.createdAt === "neznano" ? "neznano" : new Date(summary.createdAt).toLocaleString("sl-SI");
      fileMeta.textContent = `Ustvarjen: ${created} • zapisov: ${summary.records} • velikost: ${(file.size/1024).toFixed(1)} KB`;
      confirmBox.hidden = false;
      confirmInput.focus();
    } catch (error) {
      if (error?.name === "AbortError") setStatus(status, "Izbira datoteke je preklicana.");
      else setStatus(status, error?.message || "Datoteke ni bilo mogoče odpreti.", "error");
    }
  });

  confirmInput.addEventListener("input", () => {
    confirmButton.disabled = confirmInput.value.trim() !== "OBNOVI" || !selectedFile;
  });

  confirmButton.addEventListener("click", async () => {
    if (!selectedFile || confirmInput.value.trim() !== "OBNOVI") return;
    createButton.disabled = true;
    restoreButton.disabled = true;
    confirmButton.disabled = true;
    setStatus(status, "Preverjam backup, ustvarjam varnostno kopijo trenutnega stanja in obnavljam podatke …");
    try {
      const result = await restoreFile(selectedFile);
      setStatus(status, `${result.message} Obnovljenih zapisov: ${result.restored_records}. Varnostna kopija prejšnjega stanja: ${result.safety_backup}. GrowMaster se bo osvežil.`, "success");
      setTimeout(() => window.location.reload(), 1800);
    } catch (error) {
      setStatus(status, error?.message || "Obnova ni uspela.", "error");
      createButton.disabled = false;
      restoreButton.disabled = false;
      confirmButton.disabled = false;
    }
  });
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
