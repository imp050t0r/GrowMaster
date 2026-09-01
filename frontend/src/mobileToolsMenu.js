const STYLE_ID = "gm-mobile-tools-style";
const BUTTON_ID = "gm-mobile-tools-launch";
const PANEL_ID = "gm-mobile-tools-panel";

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  document.head.insertAdjacentHTML("beforeend", `<style id="${STYLE_ID}">
    #${BUTTON_ID},#${PANEL_ID}{display:none}
    @media (max-width:760px){
      .growmaster-pos-launcher,#gm-seed-button,#gm-seed-web-btn,.gm-backup-launch{display:none!important}
      #${BUTTON_ID}{
        display:flex;position:fixed;right:12px;bottom:calc(94px + env(safe-area-inset-bottom));z-index:1260;
        align-items:center;gap:7px;border:0;border-radius:999px;padding:11px 15px;background:#143c2f;color:#fff;
        font:800 14px/1 system-ui,-apple-system,"Segoe UI",sans-serif;box-shadow:0 8px 26px rgba(0,0,0,.24);cursor:pointer
      }
      #${PANEL_ID}.open{display:flex}
      #${PANEL_ID}{position:fixed;inset:0;z-index:1500;align-items:flex-end;background:rgba(7,17,13,.54);backdrop-filter:blur(3px)}
      .gm-mobile-tools-sheet{width:100%;box-sizing:border-box;background:#f7f4ec;border-radius:22px 22px 0 0;padding:18px 16px calc(18px + env(safe-area-inset-bottom));box-shadow:0 -16px 44px rgba(0,0,0,.28)}
      .gm-mobile-tools-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}
      .gm-mobile-tools-head h2{margin:0;color:#143c2f;font-size:21px}.gm-mobile-tools-close{border:0;background:#e9e4d9;color:#143c2f;border-radius:999px;width:38px;height:38px;font-size:24px;line-height:1;cursor:pointer}
      .gm-mobile-tools-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
      .gm-mobile-tool{min-height:86px;border:1px solid #d9d4c8;border-radius:16px;background:#fff;color:#143c2f;padding:14px 12px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:7px;text-align:left;font:800 15px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;cursor:pointer;box-shadow:0 5px 16px rgba(20,60,47,.08)}
      .gm-mobile-tool-icon{font-size:25px;line-height:1}.gm-mobile-tool small{font-size:11px;font-weight:600;color:#6c6a63}
    }
  </style>`);
}

function closeMenu() {
  document.getElementById(PANEL_ID)?.classList.remove("open");
}

function openMenu() {
  document.getElementById(PANEL_ID)?.classList.add("open");
}

function openSeedCenter() {
  closeMenu();
  if (window.GrowMasterSeedCenter?.open) window.GrowMasterSeedCenter.open("forecast");
  else document.getElementById("gm-seed-button")?.click();
}

function openSeedOnline() {
  closeMenu();
  if (window.GrowMasterSeedSearch?.open) window.GrowMasterSeedSearch.open();
  else document.getElementById("gm-seed-web-btn")?.click();
}

function openBackup() {
  closeMenu();
  document.getElementById("gm-backup-launch")?.click();
}

function openPos() {
  window.location.assign("/pos.html");
}

function install() {
  if (document.getElementById(BUTTON_ID)) return;
  installStyles();
  document.body.insertAdjacentHTML("beforeend", `
    <button id="${BUTTON_ID}" type="button" aria-haspopup="dialog" aria-controls="${PANEL_ID}">☰ ORODJA</button>
    <aside id="${PANEL_ID}" role="dialog" aria-modal="true" aria-label="GrowMaster orodja">
      <div class="gm-mobile-tools-sheet">
        <div class="gm-mobile-tools-head"><h2>Orodja</h2><button class="gm-mobile-tools-close" type="button" aria-label="Zapri">×</button></div>
        <div class="gm-mobile-tools-grid">
          <button class="gm-mobile-tool" type="button" data-tool="pos"><span class="gm-mobile-tool-icon">🧾</span><span>POS</span><small>Prodaja na lokaciji</small></button>
          <button class="gm-mobile-tool" type="button" data-tool="seed"><span class="gm-mobile-tool-icon">🌱</span><span>Seme</span><small>Seed Center in zaloga</small></button>
          <button class="gm-mobile-tool" type="button" data-tool="seed-online"><span class="gm-mobile-tool-icon">🌐</span><span>Seme online</span><small>Dobavitelji in nabava</small></button>
          <button class="gm-mobile-tool" type="button" data-tool="backup"><span class="gm-mobile-tool-icon">💾</span><span>Backup</span><small>Varnostna kopija in obnova</small></button>
        </div>
      </div>
    </aside>`);

  const panel = document.getElementById(PANEL_ID);
  document.getElementById(BUTTON_ID)?.addEventListener("click", openMenu);
  panel?.querySelector(".gm-mobile-tools-close")?.addEventListener("click", closeMenu);
  panel?.addEventListener("click", (event) => {
    if (event.target === panel) { closeMenu(); return; }
    const tool = event.target.closest("[data-tool]")?.dataset.tool;
    if (tool === "pos") openPos();
    else if (tool === "seed") openSeedCenter();
    else if (tool === "seed-online") openSeedOnline();
    else if (tool === "backup") openBackup();
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeMenu(); });
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
else install();
