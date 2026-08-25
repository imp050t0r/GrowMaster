import { apiRequest } from "./platform";

const CARD_ID = "gm-sowing-dashboard-card";
const STYLE_ID = "gm-sowing-dashboard-style";
let loading = false;
let lastLoadedAt = 0;

if (!document.getElementById(STYLE_ID)) {
  document.head.insertAdjacentHTML("beforeend", `<style id="${STYLE_ID}">
  #${CARD_ID}{margin-bottom:18px;border:1px solid #d9d4c8;background:linear-gradient(135deg,#eef5ef,#fff);border-radius:18px;padding:18px;box-shadow:0 8px 24px #143c2f0d}
  .gm-sow-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:12px}.gm-sow-head h2{margin:2px 0 4px}.gm-sow-head p{margin:0;color:#6a675f}.gm-sow-kicker{font-size:11px;font-weight:900;letter-spacing:.09em;text-transform:uppercase;color:#617268}.gm-sow-actions{display:flex;gap:8px;flex-wrap:wrap}.gm-sow-button{border:0;border-radius:9px;padding:9px 12px;font-weight:800;cursor:pointer;background:#143c2f;color:#fff}.gm-sow-button.secondary{background:#e8e3d8;color:#143c2f}
  .gm-sow-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:12px 0}.gm-sow-metric{background:#fff;border:1px solid #e3dfd5;border-radius:12px;padding:10px}.gm-sow-metric span{display:block;font-size:12px;color:#6b6861}.gm-sow-metric strong{display:block;margin-top:2px;font-size:23px;color:#143c2f}.gm-sow-metric.warn strong{color:#9a6a00}.gm-sow-metric.block strong{color:#a53024}
  .gm-sow-section{margin-top:14px}.gm-sow-section h3{margin:0 0 7px;color:#143c2f}.gm-sow-list{display:grid;gap:8px}.gm-sow-row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;background:#fff;border:1px solid #e3dfd5;border-radius:11px;padding:11px 12px}.gm-sow-date{font-weight:900;color:#143c2f;min-width:54px}.gm-sow-main strong{display:block}.gm-sow-main small{display:block;color:#6b6861;margin-top:2px;line-height:1.35}.gm-sow-status{font-size:12px;font-weight:900;white-space:nowrap}.gm-sow-status.READY{color:#17633c}.gm-sow-status.ATTENTION{color:#9a6a00}.gm-sow-status.BLOCKED{color:#a53024}.gm-sow-reasons{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}.gm-sow-chip{font-size:11px;padding:3px 7px;border-radius:999px;background:#eef2ee;color:#315143}.gm-sow-chip.warn{background:#fff0ce;color:#705000}.gm-sow-chip.block{background:#ffe1dc;color:#8c2b20}.gm-sow-empty{background:#fff;border:1px dashed #d6d0c5;border-radius:12px;padding:18px;color:#666;text-align:center}.gm-sow-note{margin-top:9px;padding:9px 11px;border-radius:10px;background:#edf2f4;color:#4c5a60;font-size:13px}
  @media(max-width:760px){.gm-sow-head{display:grid}.gm-sow-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.gm-sow-row{grid-template-columns:auto 1fr}.gm-sow-status{grid-column:2}.gm-sow-metric strong{font-size:20px}}
  </style>`);
}

function esc(value) { return String(value ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m])); }
function shortDate(value) { if (!value) return "—"; const p=String(value).split("-"); return p.length===3?`${Number(p[2])}.${Number(p[1])}.`:String(value); }
function dateIso(d){ return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`; }
function asMonths(value){ if(Array.isArray(value)) return value.map(Number); if(typeof value==="string") return value.split(/[^0-9]+/).filter(Boolean).map(Number); return []; }
function familyKey(value){ return String(value||"").trim().toLocaleLowerCase("sl"); }

function flattenForecast(data){
  const rows=[];
  for(const item of data.items||[]){
    for(const plan of item.plans||[]){
      rows.push({...plan,crop:item.crop,variety:item.variety,seed_status:item.status,unit:item.unit,required_quantity:plan.required_quantity ?? plan.reserved_quantity ?? null});
    }
  }
  return rows;
}

function buildQueue(forecast, plans, crops, beds, plantings){
  const cropById=new Map((crops||[]).map(c=>[String(c.id),c]));
  const bedById=new Map((beds||[]).map(b=>[String(b.id),b]));
  const planById=new Map((plans||[]).map(p=>[String(p.id),p]));
  const activeByBed=new Map();
  for(const p of plantings||[]){ if(p.status==="active") activeByBed.set(String(p.bed_id),p); }
  const warningPlanIds=new Set((forecast.warnings||[]).map(w=>String(w.crop_plan_id)));
  const today=dateIso(new Date());
  return flattenForecast(forecast).map(row=>{
    const plan=planById.get(String(row.crop_plan_id))||{};
    const crop=cropById.get(String(plan.crop_id)) || (crops||[]).find(c=>c.name===row.crop) || {};
    const variety=(crop.varieties||[]).find(v=>String(v.id)===String(plan.variety_id)) || (crop.varieties||[]).find(v=>v.name===row.variety) || {};
    const bed=bedById.get(String(plan.bed_id)) || (beds||[]).find(b=>b.name===row.bed) || {};
    const active=activeByBed.get(String(bed.id));
    const reasons=[]; let status="READY";
    const block=(text)=>{status="BLOCKED";reasons.push({level:"block",text});};
    const warn=(text)=>{if(status!=="BLOCKED")status="ATTENTION";reasons.push({level:"warn",text});};
    const ok=(text)=>reasons.push({level:"ok",text});

    if(row.seed_status==="ORDER") block("seme je treba naročiti");
    else if(row.seed_status==="LOW_STOCK") warn("nizka zaloga semena");
    else ok("seme pripravljeno");
    if(warningPlanIds.has(String(row.crop_plan_id))) warn("manjka setvena norma");

    const lastFamily=familyKey(bed.last_crop_family); const nextFamily=familyKey(crop.family);
    if(lastFamily && nextFamily && lastFamily===nextFamily) block(`kolobar: ponovitev ${crop.family}`);
    else if(lastFamily && nextFamily) ok("kolobar: druga družina");
    else warn("kolobar ni popolnoma preverljiv");

    if(active && String(active.expected_harvest_date||"") >= String(row.sowing_date||"")) block(`gredica zasedena do ${shortDate(active.expected_harvest_date)}`);
    else if(active) warn("prejšnja kultura mora biti pravočasno pospravljena");
    else ok("gredica prosta");

    const months=asMonths(variety.outdoor_months); const month=Number(String(row.sowing_date||"").slice(5,7));
    if(months.length && !months.includes(month)) warn("termin izven outdoor koledarja");
    else if(months.length) ok("termin sezonsko primeren");
    else warn("sezonski koledar ni določen");

    return {...row,status,reasons,is_today:String(row.sowing_date)===today,bed_id:bed.id,crop_family:crop.family};
  }).sort((a,b)=>String(a.sowing_date).localeCompare(String(b.sowing_date))||String(a.bed).localeCompare(String(b.bed)));
}

function renderRows(items){
  if(!items.length) return `<div class="gm-sow-empty">Ni setev v tem obdobju.</div>`;
  return `<div class="gm-sow-list">${items.map(item=>`<div class="gm-sow-row"><div class="gm-sow-date">${esc(shortDate(item.sowing_date))}</div><div class="gm-sow-main"><strong>${esc(item.crop)} · ${esc(item.variety)}</strong><small>Gredica ${esc(item.bed)}${item.required_quantity!=null?` · ${Number(item.required_quantity).toLocaleString("sl-SI",{maximumFractionDigits:2})} ${esc(item.unit)} semena`:""}</small><div class="gm-sow-reasons">${item.reasons.slice(0,4).map(r=>`<span class="gm-sow-chip ${r.level}">${esc(r.text)}</span>`).join("")}</div></div><div class="gm-sow-status ${item.status}">${item.status==="READY"?"POSEJ":item.status==="ATTENTION"?"PREVERI":"USTAVI"}</div></div>`).join("")}</div>`;
}

function render(card, queue){
  const todayRows=queue.filter(i=>i.is_today); const weekRows=queue.filter(i=>!i.is_today);
  const ready=queue.filter(i=>i.status==="READY").length; const attention=queue.filter(i=>i.status==="ATTENTION").length; const blocked=queue.filter(i=>i.status==="BLOCKED").length;
  card.innerHTML=`<div class="gm-sow-head"><div><span class="gm-sow-kicker">Operativni plan · 7 dni</span><h2>🗓️ Kaj posejati danes / ta teden</h2><p>Crop Plan + kolobar + sezonski termin + prosta gredica + zaloga semena.</p></div><div class="gm-sow-actions"><button type="button" class="gm-sow-button secondary" data-gm-sow-refresh>OSVEŽI</button><button type="button" class="gm-sow-button" data-gm-sow-seed>SEED CENTER</button></div></div><div class="gm-sow-metrics"><div class="gm-sow-metric"><span>Skupaj</span><strong>${queue.length}</strong></div><div class="gm-sow-metric"><span>Pripravljeno</span><strong>${ready}</strong></div><div class="gm-sow-metric warn"><span>Preveri</span><strong>${attention}</strong></div><div class="gm-sow-metric block"><span>Blokirano</span><strong>${blocked}</strong></div></div><div class="gm-sow-section"><h3>Danes</h3>${renderRows(todayRows)}</div><div class="gm-sow-section"><h3>Preostanek tedna</h3>${renderRows(weekRows)}</div><div class="gm-sow-note">Vreme še ni povezano z GrowMasterjem, zato kartica ne blokira setve zaradi dežja, vetra ali temperature. Ko bo dodan weather provider, ga lahko vključimo kot dodatni kriterij pripravljenosti.</div>`;
  card.querySelector("[data-gm-sow-refresh]")?.addEventListener("click",()=>refresh(true));
  card.querySelector("[data-gm-sow-seed]")?.addEventListener("click",()=>window.GrowMasterSeedCenter?.open?.("forecast"));
}

function anchor(){ return document.getElementById("gm-seed-dashboard-card") || document.querySelector(".smart-review-panel"); }
async function refresh(force=false){
  const a=anchor(); if(!a||loading) return; if(!force&&Date.now()-lastLoadedAt<60000&&document.getElementById(CARD_ID)) return;
  loading=true; let card=document.getElementById(CARD_ID); if(!card){card=document.createElement("section");card.id=CARD_ID;card.className="panel";a.parentElement?.insertBefore(card,a.nextSibling);} card.innerHTML=`<div class="gm-sow-empty">Sestavljam operativni setveni seznam …</div>`;
  try{
    const [forecast,plans,crops,beds,plantings]=await Promise.all([apiRequest("/api/seed-inventory/forecast?horizon_days=7"),apiRequest("/api/plans"),apiRequest("/api/crops"),apiRequest("/api/beds"),apiRequest("/api/plantings")]);
    render(card,buildQueue(forecast,plans,crops,beds,plantings)); lastLoadedAt=Date.now();
  }catch(error){card.innerHTML=`<div class="gm-sow-note">Operativni setveni seznam trenutno ni na voljo: ${esc(error.message||"napaka pri povezavi")}</div>`;}finally{loading=false;}
}
function sync(){const a=anchor();const card=document.getElementById(CARD_ID);if(!a){card?.remove();return;}refresh(false);}
const observer=new MutationObserver(sync);observer.observe(document.getElementById("root")||document.body,{childList:true,subtree:true});window.setTimeout(sync,1100);window.addEventListener("focus",()=>refresh(false));window.addEventListener("growmaster:seed-changed",()=>refresh(true));
