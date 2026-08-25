import { apiRequest } from "./platform";

const state = { open: false, tab: "forecast", data: {}, loading: false, error: "" };

const css = `
#gm-seed-button{position:fixed;right:18px;bottom:82px;z-index:1200;border:0;border-radius:999px;background:#143c2f;color:white;padding:12px 17px;font-weight:800;box-shadow:0 8px 28px #0003;cursor:pointer}
#gm-seed-center{position:fixed;inset:0;z-index:1300;background:#0c1813aa;display:none;align-items:stretch;justify-content:flex-end}.gm-seed-open{display:flex!important}
.gm-seed-shell{width:min(780px,100%);height:100%;overflow:auto;background:#f7f4ec;padding:20px;box-shadow:-10px 0 40px #0004}.gm-seed-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.gm-seed-head h2{margin:0;color:#143c2f}.gm-seed-close{font-size:26px;border:0;background:transparent;cursor:pointer}
.gm-seed-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:18px 0}.gm-seed-tabs button{border:1px solid #c9c4b7;border-radius:999px;background:white;padding:8px 12px;cursor:pointer}.gm-seed-tabs button.active{background:#143c2f;color:white;border-color:#143c2f}
.gm-seed-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:12px 0}.gm-seed-card,.gm-seed-row{background:white;border:1px solid #ded9cd;border-radius:14px;padding:13px}.gm-seed-card strong{font-size:24px;display:block}.gm-seed-list{display:grid;gap:9px}.gm-seed-row{display:grid;grid-template-columns:1fr auto;gap:8px}.gm-seed-row small{color:#69665f}.gm-seed-status{font-weight:800}.gm-ORDER{color:#a53024}.gm-LOW_STOCK{color:#9a6a00}.gm-OK{color:#17633c}.gm-seed-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;background:white;padding:14px;border-radius:14px;border:1px solid #ded9cd}.gm-seed-form label{display:grid;gap:4px;font-size:12px;font-weight:700}.gm-seed-form input,.gm-seed-form select{padding:9px;border:1px solid #c8c3b7;border-radius:8px}.gm-seed-form button{grid-column:1/-1;padding:10px;border:0;border-radius:9px;background:#143c2f;color:white;font-weight:800}.gm-seed-warn{padding:10px;border-radius:10px;background:#fff0ce;color:#705000}.gm-seed-error{padding:10px;border-radius:10px;background:#ffe1dc;color:#8c2b20}@media(max-width:600px){.gm-seed-shell{padding:14px}.gm-seed-form{grid-template-columns:1fr}#gm-seed-button{bottom:72px;right:12px}}
`;

document.head.insertAdjacentHTML("beforeend", `<style>${css}</style>`);
document.body.insertAdjacentHTML("beforeend", `<button id="gm-seed-button" type="button">🌱 Seme</button><aside id="gm-seed-center"><div class="gm-seed-shell"><div class="gm-seed-head"><div><small>GrowMaster</small><h2>Seed Center</h2></div><button class="gm-seed-close" aria-label="Zapri">×</button></div><div class="gm-seed-tabs"></div><div id="gm-seed-content"></div></div></aside>`);

const root = document.getElementById("gm-seed-center");
const content = document.getElementById("gm-seed-content");
const tabs = [
  ["forecast","Napoved"],["inventory","Zaloga"],["reservations","Rezervirano"],["orders","Naročila"],["quality","Podatki"],["learning","Učenje"]
];

function n(value, digits=1){ return Number(value || 0).toLocaleString("sl-SI",{maximumFractionDigits:digits}); }
function esc(value){ return String(value ?? "").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m])); }
function statusLabel(s){ return ({ORDER:"NAROČI",LOW_STOCK:"NIZKA ZALOGA",OK:"OK"}[s]||s); }

function drawTabs(){ document.querySelector(".gm-seed-tabs").innerHTML=tabs.map(([k,l])=>`<button data-tab="${k}" class="${state.tab===k?"active":""}">${l}</button>`).join(""); }
function metrics(values){ return `<div class="gm-seed-metrics">${values.map(([l,v,c=""])=>`<div class="gm-seed-card"><small>${l}</small><strong class="${c}">${v}</strong></div>`).join("")}</div>`; }
function rows(items, builder){ return `<div class="gm-seed-list">${items.map(builder).join("") || `<div class="gm-seed-card">Ni zapisov.</div>`}</div>`; }

function render(){
  drawTabs();
  if(state.loading){content.innerHTML=`<div class="gm-seed-card">Nalagam …</div>`;return;}
  if(state.error){content.innerHTML=`<div class="gm-seed-error">${esc(state.error)}</div>`;return;}
  const d=state.data;
  if(state.tab==="forecast"){
    const s=d.summary||{}; content.innerHTML=metrics([["OK",s.ok||0,"gm-OK"],["Nizka",s.low_stock||0,"gm-LOW_STOCK"],["Naroči",s.order||0,"gm-ORDER"],["Brez norme",s.missing_seed_rate||0]])+rows(d.items||[],i=>`<div class="gm-seed-row"><div><strong>${esc(i.crop)} · ${esc(i.variety)}</strong><small>${n(i.required_quantity)} ${i.unit} potrebno · ${n(i.available_quantity)} na zalogi</small></div><div class="gm-seed-status gm-${i.status}">${statusLabel(i.status)}</div></div>`);
  } else if(state.tab==="inventory"){
    content.innerHTML=`<form id="gm-seed-add" class="gm-seed-form"><label>Kultura<input name="crop" required></label><label>Sorta<input name="variety"></label><label>Enota<select name="unit"><option value="g">g</option><option value="seeds">semena</option><option value="pellets">peleti</option></select></label><label>Količina<input name="quantity" type="number" min="0" step="0.01" required></label><label>Velikost paketa<input name="package_size" type="number" min="0" step="0.01"></label><label>TKW/TSW g/1000<input name="thousand_seed_weight_g" type="number" min="0" step="0.001"></label><label>Kalivost %<input name="germination_pct" type="number" value="95" min="1" max="100"></label><label>Vznik %<input name="field_emergence_pct" type="number" value="90" min="1" max="100"></label><label>Dobavitelj<input name="supplier"></label><label>Lot<input name="lot_number"></label><button>Dodaj semensko serijo</button></form><br>`+metrics([["Serije",d.lot_count||0]])+rows(d.lots||[],i=>`<div class="gm-seed-row"><div><strong>${esc(i.crop)} ${esc(i.variety||"")}</strong><small>${esc(i.supplier||"brez dobavitelja")} · lot ${esc(i.lot_number||"—")}</small></div><div><strong>${n(i.quantity,2)} ${esc(i.unit)}</strong></div></div>`);
  } else if(state.tab==="reservations"){
    const s=d.summary||{}; content.innerHTML=metrics([["Proste",s.ok||0,"gm-OK"],["Nizke",s.low_stock||0,"gm-LOW_STOCK"],["Primanjkljaj",s.order||0,"gm-ORDER"]])+rows(d.items||[],i=>`<div class="gm-seed-row"><div><strong>${esc(i.crop)} · ${esc(i.variety)}</strong><small>fizično ${n(i.physical_quantity)} · rezervirano ${n(i.reserved_quantity)} · prosto ${n(i.free_quantity)} ${i.unit}</small></div><div class="gm-seed-status gm-${i.status}">${statusLabel(i.status)}</div></div>`);
  } else if(state.tab==="orders"){
    content.innerHTML=metrics([["Osnutki",d.count||0]])+rows(d.drafts||[],i=>`<div class="gm-seed-row"><div><strong>${esc(i.crop)} · ${esc(i.variety)}</strong><small>${i.packages_to_order||"?"} paketov · ${n(i.order_quantity)} ${i.unit} · ${esc(i.supplier_hint||"dobavitelj ni povezan")}</small></div><div class="gm-seed-status ${i.ready_for_purchase_order?"gm-OK":"gm-LOW_STOCK"}">${i.ready_for_purchase_order?"PRIPRAVLJENO":"DOPOLNI NABAVO"}</div></div>`);
  } else if(state.tab==="quality"){
    const s=d.summary||{}; content.innerHTML=metrics([["Popolni",s.complete||0,"gm-OK"],["Delni",s.partial||0,"gm-LOW_STOCK"],["Nepopolni",s.incomplete||0,"gm-ORDER"]])+rows((d.items||[]).slice(0,100),i=>`<div class="gm-seed-row"><div><strong>${esc(i.crop)} · ${esc(i.variety)}</strong><small>manjka: ${esc((i.missing||[]).join(", ")||"nič")}</small></div><div><strong>${i.score}%</strong></div></div>`);
  } else {
    content.innerHTML=metrics([["Predlogi",d.count||0]])+`<p class="gm-seed-warn">GrowMaster predlaga popravke šele iz več dejanskih ciklov. Ne prepisuje master podatkov tiho.</p>`+rows(d.suggestions||[],i=>`<div class="gm-seed-row"><div><strong>${esc(i.crop)} · ${esc(i.variety)}</strong><small>${i.samples} ciklov · DTM ${i.current_days_to_harvest} → ${i.observed_days_to_harvest??"—"} · norma ${i.current_seed_rate_g_m2??"—"} → ${i.observed_seed_rate_g_m2??"—"} g/m²</small></div><div><strong>${esc(i.confidence)}</strong></div></div>`);
  }
}

async function load(){
  state.loading=true; state.error=""; render();
  const paths={forecast:"/api/seed-inventory/forecast",inventory:"/api/seed-inventory",reservations:"/api/seed-inventory/reservations",orders:"/api/seed-inventory/purchase-drafts",quality:"/api/master-data/quality",learning:"/api/agronomy/learning"};
  try{ state.data=await apiRequest(paths[state.tab]); }catch(e){ state.error=e.message||"Seed Center ni dosegljiv. Prijavi se v GrowMaster."; }finally{state.loading=false;render();}
}

document.getElementById("gm-seed-button").addEventListener("click",()=>{state.open=true;root.classList.add("gm-seed-open");load();});
document.querySelector(".gm-seed-close").addEventListener("click",()=>root.classList.remove("gm-seed-open"));
document.querySelector(".gm-seed-tabs").addEventListener("click",e=>{const b=e.target.closest("[data-tab]");if(!b)return;state.tab=b.dataset.tab;load();});
content.addEventListener("submit",async e=>{if(e.target.id!=="gm-seed-add")return;e.preventDefault();const f=new FormData(e.target);const obj=Object.fromEntries(f.entries());for(const k of ["quantity","package_size","thousand_seed_weight_g","germination_pct","field_emergence_pct"]){obj[k]=obj[k]?Number(obj[k]):null;}try{await apiRequest("/api/seed-inventory/lots",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(obj)});await load();}catch(err){state.error=err.message;render();}});
