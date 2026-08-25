import { apiRequest } from "./platform";

const state = { status: null, open: false, error: "", notice: "" };

const css = `
#gm-license-badge{position:fixed;right:16px;top:14px;z-index:1250;border:0;border-radius:999px;padding:8px 12px;font-weight:900;cursor:pointer;box-shadow:0 5px 18px #0002;background:#fff;color:#143c2f;border:1px solid #d4cec1}
#gm-license-badge.gm-trial-expired{background:#a53024;color:#fff;border-color:#a53024}#gm-license-badge.gm-pro{background:#143c2f;color:#fff;border-color:#143c2f}#gm-license-badge.gm-admin{background:#392f5a;color:#fff;border-color:#392f5a}
#gm-license-center{position:fixed;inset:0;z-index:1600;background:#07110dcc;display:none;align-items:center;justify-content:center;padding:18px;backdrop-filter:blur(3px)}#gm-license-center.open{display:flex}
.gm-license-card{width:min(610px,100%);max-height:90vh;overflow:auto;background:#f7f4ec;border-radius:18px;padding:22px;box-shadow:0 24px 70px #0006}.gm-license-head{display:flex;justify-content:space-between;gap:16px}.gm-license-head h2{margin:0;color:#143c2f}.gm-license-close{border:0;background:transparent;font-size:28px;cursor:pointer}.gm-license-kicker{font-size:11px;text-transform:uppercase;letter-spacing:.09em;font-weight:900;color:#6b7a72}.gm-license-mode{font-size:32px;font-weight:950;margin:15px 0 3px;color:#143c2f}.gm-license-muted{color:#69665f;font-size:13px;line-height:1.45}.gm-license-code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;background:#fff;border:1px solid #d8d2c6;border-radius:10px;padding:11px;overflow-wrap:anywhere;margin:8px 0}.gm-license-form{display:grid;gap:9px;margin-top:18px}.gm-license-form textarea{min-height:110px;resize:vertical;padding:10px;border:1px solid #c8c3b7;border-radius:9px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}.gm-license-action{border:0;border-radius:9px;background:#143c2f;color:#fff;padding:10px 13px;font-weight:900;cursor:pointer}.gm-license-secondary{background:#e7e2d6;color:#143c2f}.gm-license-actions{display:flex;gap:8px;flex-wrap:wrap}.gm-license-notice,.gm-license-error,.gm-license-warning{padding:10px 12px;border-radius:10px;margin-top:12px}.gm-license-notice{background:#dff3e6;color:#195d38}.gm-license-error{background:#ffe1dc;color:#8c2b20}.gm-license-warning{background:#fff0ce;color:#705000}.gm-license-lock{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:1240;background:#a53024;color:#fff;border-radius:12px;padding:10px 14px;font-weight:800;box-shadow:0 8px 24px #0003;cursor:pointer;display:none;text-align:center}.gm-license-lock.show{display:block}
@media(max-width:650px){#gm-license-badge{right:10px;top:8px}.gm-license-card{padding:17px}.gm-license-mode{font-size:26px}.gm-license-lock{width:calc(100% - 24px)}}
`;

document.head.insertAdjacentHTML("beforeend", `<style>${css}</style>`);
document.body.insertAdjacentHTML("beforeend", `
<button id="gm-license-badge" type="button">LICENCA</button>
<div id="gm-license-lock" class="gm-license-lock">Testno obdobje je poteklo · AKTIVIRAJ PRO</div>
<aside id="gm-license-center" role="dialog" aria-modal="true" aria-label="GrowMaster licenca">
  <div class="gm-license-card">
    <div class="gm-license-head"><div><div class="gm-license-kicker">GrowMaster licenca</div><h2>Aktivacija</h2></div><button class="gm-license-close" type="button">×</button></div>
    <div id="gm-license-content"></div>
  </div>
</aside>`);

const root = document.getElementById("gm-license-center");
const badge = document.getElementById("gm-license-badge");
const lock = document.getElementById("gm-license-lock");
const content = document.getElementById("gm-license-content");

function esc(value) { return String(value ?? "").replace(/[&<>"']/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m])); }
function label(s) { return ({trial:"TRIAL",trial_expired:"TRIAL POTEKEL",pro:"PRO",admin:"ADMIN"}[s?.mode] || "LICENCA"); }

function render() {
  const s = state.status;
  if (!s) return;
  badge.textContent = s.mode === "trial" ? `TRIAL · ${s.trial_days_left} dni` : label(s);
  badge.className = `gm-${s.mode.replaceAll("_", "-")}`;
  lock.classList.toggle("show", s.mode === "trial_expired");
  const activeText = s.mode === "trial"
    ? `Polna testna uporaba je omogočena še ${s.trial_days_left} dni.`
    : s.mode === "trial_expired"
      ? "Podatki ostanejo dostopni za pregled, spreminjanje pa je zaklenjeno do aktivacije Pro licence."
      : `Aktivna je GrowMaster ${label(s)} licenca${s.customer ? ` za ${esc(s.customer)}` : ""}.`;
  content.innerHTML = `
    <div class="gm-license-mode">${label(s)}</div>
    <div class="gm-license-muted">${activeText}</div>
    ${s.license_error ? `<div class="gm-license-warning">Shranjena licenca ni veljavna: ${esc(s.license_error)}</div>` : ""}
    ${state.notice ? `<div class="gm-license-notice">${esc(state.notice)}</div>` : ""}
    ${state.error ? `<div class="gm-license-error">${esc(state.error)}</div>` : ""}
    <h3>Aktivacijska koda te naprave</h3>
    <div class="gm-license-code">${esc(s.activation_request_code)}</div>
    <div class="gm-license-actions"><button id="gm-copy-code" class="gm-license-action gm-license-secondary" type="button">KOPIRAJ KODO</button></div>
    ${s.mode === "pro" || s.mode === "admin" ? `<p class="gm-license-muted">ID licence: ${esc(s.license_id || "—")}<br>Veljavnost: ${esc(s.expires_at || "brez časovne omejitve")}</p>` : `
      <form id="gm-license-form" class="gm-license-form">
        <label><strong>Podpisana licenca</strong><textarea name="token" required placeholder="Prilepi GrowMaster licenčni niz …"></textarea></label>
        <button class="gm-license-action" type="submit">AKTIVIRAJ GROWMASTER</button>
      </form>`}
    <p class="gm-license-muted">Licenca se preverja lokalno z Ed25519 podpisom. Zasebni podpisni ključ ni shranjen v aplikaciji.</p>`;
}

async function refresh() {
  try {
    state.status = await apiRequest("/api/license/status", { method: "GET" });
    state.error = "";
    render();
  } catch (e) {
    state.error = e?.message || "Status licence ni dosegljiv.";
  }
}

function open() { state.open = true; root.classList.add("open"); render(); }
function close() { state.open = false; root.classList.remove("open"); }

badge.addEventListener("click", open);
lock.addEventListener("click", open);
document.querySelector(".gm-license-close").addEventListener("click", close);
root.addEventListener("click", e => { if (e.target === root) close(); });
document.addEventListener("keydown", e => { if (e.key === "Escape" && state.open) close(); });

content.addEventListener("click", async e => {
  if (e.target?.id === "gm-copy-code" && state.status) {
    await navigator.clipboard?.writeText(state.status.activation_request_code);
    state.notice = "Aktivacijska koda je kopirana.";
    render();
  }
});
content.addEventListener("submit", async e => {
  if (e.target?.id !== "gm-license-form") return;
  e.preventDefault(); state.error = ""; state.notice = "";
  const token = new FormData(e.target).get("token")?.trim();
  try {
    state.status = await apiRequest("/api/license/activate", { method: "POST", body: JSON.stringify({ token }) });
    state.notice = "Aktivacija je uspela.";
  } catch (err) {
    state.error = err?.message || "Aktivacija ni uspela.";
  }
  render();
});

window.addEventListener("growmaster:open-license", open);
refresh();
setInterval(refresh, 15 * 60 * 1000);
