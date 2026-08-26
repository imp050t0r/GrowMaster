import { apiFetch } from "./platform";

const css = `
.gm-backup-launch{position:fixed;left:18px;bottom:18px;z-index:9000;border:1px solid #143c2f;background:#fff;color:#143c2f;border-radius:999px;padding:10px 14px;font-weight:800;box-shadow:0 8px 24px rgba(0,0,0,.14);cursor:pointer}
.gm-backup-backdrop{position:fixed;inset:0;z-index:9999;background:rgba(15,24,20,.5);display:flex;align-items:center;justify-content:center;padding:18px}.gm-backup-modal{width:min(660px,100%);background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.28)}.gm-backup-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:20px 22px;border-bottom:1px solid #e8e5de}.gm-backup-head h3{margin:0 0 5px}.gm-backup-head p{margin:0;color:#666;font-size:13px;line-height:1.45}.gm-backup-close{border:0;background:transparent;font-size:24px;cursor:pointer}.gm-backup-body{padding:22px}.gm-backup-btn{border:1px solid #143c2f;background:#143c2f;color:#fff;border-radius:9px;padding:11px 15px;font-weight:800;cursor:pointer}.gm-backup-btn:disabled{opacity:.55;cursor:default}.gm-backup-note{margin:14px 0 0;color:#666;font-size:13px;line-height:1.5}.gm-backup-status{margin-top:16px;padding:12px 14px;border-radius:10px;background:#f7f5ef;color:#333;font-size:13px;line-height:1.45}.gm-backup-status[data-kind="error"]{background:#fff1f1;color:#8a2525}.gm-backup-status[data-kind="success"]{background:#eef8f1;color:#1f6638}
`;
document.head.insertAdjacentHTML("beforeend", `<style>${css}</style>`);

function suggestedBackupName() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  const stamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}_${pad(now.getHours())}-${pad(now.getMinutes())}`;
  return `GrowMaster-backup-${stamp}.json`;
}

async function fetchBackupBlob() {
  const response = await apiFetch("/api/system/backups/export");
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "Backupa ni bilo mogoče ustvariti.");
  }
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
  const name = suggestedBackupName();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

function setStatus(status, message, kind = "") {
  status.hidden = false;
  status.dataset.kind = kind;
  status.textContent = message;
}

function openBackupCenter() {
  const backdrop = document.createElement("div");
  backdrop.className = "gm-backup-backdrop";
  backdrop.innerHTML = `<div class="gm-backup-modal"><div class="gm-backup-head"><div><h3>Backup Center</h3><p>Na računalniku sam izbereš disk, mapo in ime datoteke.</p></div><button class="gm-backup-close" type="button">×</button></div><div class="gm-backup-body"><button class="gm-backup-btn" type="button" data-create>IZBERI MESTO IN SHRANI BACKUP</button><p class="gm-backup-note">Odprlo se bo običajno Windows okno »Shrani kot«. Z miško izbereš npr. disk C:, D:, USB ključ ali zunanji disk, nato mapo in v polje »Ime datoteke« napišeš poljubno ime.</p><div class="gm-backup-status" hidden aria-live="polite"></div></div></div>`;
  document.body.appendChild(backdrop);

  const button = backdrop.querySelector("[data-create]");
  const status = backdrop.querySelector(".gm-backup-status");
  const close = () => backdrop.remove();
  backdrop.querySelector(".gm-backup-close").addEventListener("click", close);
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) close(); });

  button.addEventListener("click", async () => {
    button.disabled = true;
    status.hidden = true;

    try {
      if (window.showSaveFilePicker) {
        // Picker MUST open directly from the mouse click. The user chooses the
        // disk, folder and final file name before GrowMaster starts exporting.
        const handle = await window.showSaveFilePicker({
          suggestedName: suggestedBackupName(),
          types: [
            {
              description: "GrowMaster varnostna kopija",
              accept: { "application/json": [".json"] },
            },
          ],
        });
        setStatus(status, "Ustvarjam backup in ga zapisujem na izbrano mesto …");
        await saveWithDesktopPicker(handle);
        setStatus(status, `Backup je shranjen kot »${handle.name}« na mestu, ki si ga izbral.`, "success");
      } else {
        setStatus(status, "Brskalnik ne podpira neposredne izbire mape. Odpiram običajen prenos datoteke …");
        await fallbackDownload();
        setStatus(status, "Backup je ustvarjen. Če brskalnik vpraša za mesto shranjevanja, izberi disk, mapo in ime datoteke.", "success");
      }
    } catch (error) {
      if (error?.name === "AbortError") {
        setStatus(status, "Shranjevanje je preklicano.");
      } else {
        setStatus(status, error?.message || "Backup ni uspel.", "error");
      }
    } finally {
      button.disabled = false;
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
