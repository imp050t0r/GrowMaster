import { apiRequest } from "./platform";

const css = `
#gm-seed-web-btn{position:fixed;right:18px;bottom:132px;z-index:1189;border:0;border-radius:999px;background:#235a45;color:#fff;padding:12px 16px;font-weight:800;box-shadow:0 8px 28px #0003;cursor:pointer}
#gm-seed-web{position:fixed;inset:0;z-index:1310;background:#07110dcc;display:none;justify-content:flex-end;backdrop-filter:blur(3px)}
#gm-seed-web.open{display:flex}.gm-ss-shell{width:min(980px,100%);height:100%;overflow:auto;background:#f7f4ec;padding:20px;box-shadow:-12px 0 42px #0005}
.gm-ss-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.gm-ss-head h2{margin:0;color:#143c2f}.gm-ss-head p{margin:4px 0 0;color:#68645d}.gm-ss-close{border:0;background:transparent;font-size:28px;cursor:pointer}.gm-ss-top-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.gm-ss-form,.gm-ss-order-form,.gm-ss-receive-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:16px 0;padding:14px;background:#fff;border:1px solid #ded9cd;border-radius:14px}.gm-ss-form{grid-template-columns:1fr 1fr auto auto auto;align-items:end}.gm-ss-form label,.gm-ss-order-form label,.gm-ss-receive-form label{display:grid;gap:4px;font-size:12px;font-weight:800}.gm-ss-form input,.gm-ss-form select,.gm-ss-order-form input,.gm-ss-order-form select,.gm-ss-receive-form input{padding:10px;border:1px solid #c8c3b7;border-radius:9px;background:white;min-width:0}.gm-ss-check{display:flex!important;align-items:center;gap:6px;padding-bottom:10px}.gm-ss-search,.gm-ss-action{padding:10px 13px;border:0;border-radius:9px;background:#143c2f;color:white;font-weight:900;cursor:pointer}.gm-ss-action.secondary{background:#e7e2d6;color:#143c2f}.gm-ss-form button,.gm-ss-order-form button,.gm-ss-receive-form button{align-self:end}.gm-ss-order-form h3,.gm-ss-receive-form h3,.gm-ss-order-form p,.gm-ss-receive-form p{grid-column:1/-1;margin:0}.gm-ss-status{margin:8px 0 12px;color:#68645d}.gm-ss-error{background:#ffe1dc;color:#8c2b20;padding:10px;border-radius:10px}.gm-ss-notice{background:#dff3e6;color:#195d38;padding:10px;border-radius:10px;margin:8px 0}.gm-ss-warning{background:#fff0ce;color:#705000;padding:10px;border-radius:10px;margin:8px 0}.gm-ss-list{display:grid;gap:9px}.gm-ss-card{background:white;border:1px solid #ded9cd;border-radius:14px;padding:13px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px}.gm-ss-card h3{margin:0 0 4px;color:#143c2f;font-size:17px}.gm-ss-meta,.gm-ss-snippet{font-size:12px;color:#68645d;line-height:1.4}.gm-ss-price{font-size:20px;font-weight:900;color:#143c2f;text-align:right}.gm-ss-price.fallback{font-size:12px;color:#705000}.gm-ss-actions{display:flex;gap:7px;justify-content:flex-end;align-items:center;margin-top:8px;flex-wrap:wrap}.gm-ss-actions a,.gm-ss-actions button{border:0;border-radius:8px;padding:8px 10px;font-weight:800;text-decoration:none;cursor:pointer}.gm-ss-actions a{background:#143c2f;color:white}.gm-ss-actions button{background:#e7e2d6;color:#143c2f}.gm-ss-badge{display:inline-block;padding:2px 7px;border-radius:999px;background:#e7e2d6;margin-right:5px;font-size:11px;font-weight:800}.gm-ss-badge.warn{background:#fff0ce;color:#705000}.gm-ss-empty{padding:26px;text-align:center;background:white;border:1px dashed #cfc9bd;border-radius:14px;color:#68645d}
.gm-ss-inline{margin-top:7px;border:1px solid #9eb2a8;background:#edf4f0;color:#143c2f;border-radius:8px;padding:6px 8px;font-size:11px;font-weight:900;cursor:pointer;width:max-content;max-width:100%}
@media(max-width:760px){.gm-ss-shell{padding:14px}.gm-ss-form,.gm-ss-order-form,.gm-ss-receive-form{grid-template-columns:1fr}.gm-ss-check{padding:4px 0}.gm-ss-card{grid-template-columns:1fr}.gm-ss-price{text-align:left}#gm-seed-web-btn{right:12px;bottom:122px}}
`;

function esc(value){return String(value??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));}
function money(value){return value==null?"cena ni zaznana":`${Number(value).toLocaleString("sl-SI",{minimumFractionDigits:2,maximumFractionDigits:2})} €`;}
function today(){return new Date().toISOString().slice(0,10);}

const state={open:false,loading:false,error:"",notice:"",data:null,catalog:null,selectedOffer:null,openOrders:null,receiveOrder:null};

document.head.insertAdjacentHTML("beforeend",`<style>${css}</style>`);
document.body.insertAdjacentHTML("beforeend",`
<button id="gm-seed-web-btn" type="button">🌐 Seme online</button>
<aside id="gm-seed-web" role="dialog" aria-modal="true" aria-label="Spletno iskanje semen">
  <div class="gm-ss-shell">
    <div class="gm-ss-head"><div><h2>Dobavitelji semen</h2><p>Od spletne ponudbe do nabave in fizičnega prevzema semena.</p><div class="gm-ss-top-actions"><button class="gm-ss-action secondary" id="gm-ss-open-orders" type="button">ODPRTA NAROČILA</button></div></div><button class="gm-ss-close" type="button" aria-label="Zapri">×</button></div>
    <form class="gm-ss-form" id="gm-ss-form">
      <label>Kultura<select name="crop" required><option value="">Izberi kulturo</option></select></label>
      <label>Sorta<select name="variety" disabled><option value="">Najprej izberi kulturo</option></select></label>
      <label class="gm-ss-check"><input type="checkbox" name="eu_only" checked> samo EU</label>
      <label class="gm-ss-check"><input type="checkbox" name="refresh"> sveži podatki</label>
      <button class="gm-ss-search" type="submit">POIŠČI</button>
    </form>
    <div id="gm-ss-content"><div class="gm-ss-empty">Iz Plant DB klikni KJE KUPITI SEME ali izberi kulturo in sorto.</div></div>
  </div>
</aside>`);

const root=document.getElementById("gm-seed-web");
const form=document.getElementById("gm-ss-form");
const content=document.getElementById("gm-ss-content");

function offerPayload(o,d){return encodeURIComponent(JSON.stringify({supplier:o.supplier,title:o.title,url:o.url,price_eur:o.price_eur,crop:d.crop,variety:d.variety}));}

function selectedCrop(){
  return (state.catalog?.crops||[]).find(item=>item.name===form.elements.crop.value);
}

function renderCropOptions(selected=""){
  const crops=state.catalog?.crops||[];
  form.elements.crop.innerHTML='<option value="">Izberi kulturo</option>'+crops.map(item=>`<option value="${esc(item.name)}">${esc(item.name)}</option>`).join("");
  form.elements.crop.value=selected;
}

function renderVarietyOptions(selected=""){
  const crop=selectedCrop();
  const varieties=crop?.varieties||[];
  form.elements.variety.disabled=!crop;
  form.elements.variety.innerHTML=`<option value="">${crop?"Vse sorte":"Najprej izberi kulturo"}</option>`+varieties.map(name=>`<option value="${esc(name)}">${esc(name)}</option>`).join("");
  form.elements.variety.value=varieties.includes(selected)?selected:"";
}

async function loadCatalog(){
  if(state.catalog)return;
  state.catalog=await apiRequest("/api/seed-suppliers/catalog");
  renderCropOptions();renderVarietyOptions();
}

function render(){
  if(state.loading){content.innerHTML='<div class="gm-ss-status">Nalagam …</div>';return;}
  if(state.error){content.innerHTML=`<div class="gm-ss-error">${esc(state.error)}</div>`;return;}
  if(state.receiveOrder){renderReceive();return;}
  if(state.openOrders){renderOpenOrders();return;}
  if(state.selectedOffer){renderOrderForm();return;}
  if(!state.data)return;
  const d=state.data;
  const fallbackCount=d.fallback_count||0;
  const status=`Preverjeno ${esc(d.checked_at||"")} · ${d.offer_count||0} neposrednih zadetkov pri ${d.supplier_count||0} dobaviteljih${fallbackCount?` · ${fallbackCount} rezervnih povezav`:""}${d.cached?" · predpomnjeno":" · sveže z interneta"}`;
  const cards=(d.offers||[]).map((o)=>{
    const fallback=Boolean(o.is_fallback);
    const badges=`<span class="gm-ss-badge">${esc(o.supplier)}</span><span class="gm-ss-badge">${esc(o.country)}</span>${o.eu?'<span class="gm-ss-badge">EU</span>':''}${fallback?'<span class="gm-ss-badge warn">REZERVNO ISKANJE</span>':''}`;
    const price=fallback?'<div class="gm-ss-price fallback">NEPOSREDEN IZDELEK NI POTRJEN</div>':`<div class="gm-ss-price">${esc(money(o.price_eur))}</div>`;
    const actions=fallback?`<a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">ODPRI ISKANJE</a>`:`<button type="button" data-order-offer="${offerPayload(o,d)}">V NABAVO</button><a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">ODPRI</a>`;
    return `<article class="gm-ss-card"><div><h3>${esc(o.title)}</h3><div class="gm-ss-meta">${badges}</div><p class="gm-ss-snippet">${esc(o.snippet||"")}</p></div><div>${price}<div class="gm-ss-actions">${actions}</div></div></article>`;
  }).join("");
  const degraded=d.degraded?'<div class="gm-ss-warning">Neposrednih strani izdelkov ni bilo mogoče zanesljivo razpoznati. Rezervne povezave odprejo ciljno iskanje pri posameznem dobavitelju; iz njih ni mogoče neposredno ustvariti nabavnega naročila.</div>':"";
  content.innerHTML=`${state.notice?`<div class="gm-ss-notice">${esc(state.notice)}</div>`:""}<div class="gm-ss-status">${status}</div>${degraded}${d.note?`<div class="gm-ss-status">${esc(d.note)}</div>`:""}${cards||'<div class="gm-ss-empty">Ni najdenih ustreznih ponudb. Poskusi brez sorte ali brez filtra EU.</div>'}`;
}

function renderOrderForm(){
  const o=state.selectedOffer;
  content.innerHTML=`<form id="gm-ss-order-form" class="gm-ss-order-form"><h3>Dodaj ponudbo v GrowMaster Nabavo</h3><p>${esc(o.crop)}${o.variety?` · ${esc(o.variety)}`:""} · ${esc(o.supplier)}</p><div class="gm-ss-warning">To še NE poveča zaloge. Seme bo dodano šele ob fizičnem PREVZEMU SEMENA.</div><label>Količina semena<input name="quantity" type="number" min="0.001" step="0.001" required></label><label>Enota<select name="unit"><option value="g">g</option><option value="seeds">semena</option><option value="pellets">peleti</option></select></label><label>Skupna cena €<input name="total_price_eur" type="number" min="0.01" step="0.01" value="${o.price_eur??""}" required></label><label>Predviden prihod<input name="expected_date" type="date"></label><button class="gm-ss-action" type="submit">USTVARI NABAVNO NAROČILO</button><button class="gm-ss-action secondary" type="button" data-cancel-order>NAZAJ</button></form>`;
}

function renderOpenOrders(){
  const orders=state.openOrders.orders||[];
  content.innerHTML=`${state.notice?`<div class="gm-ss-notice">${esc(state.notice)}</div>`:""}<div class="gm-ss-status">Odprta semenska naročila: ${orders.length}. Zaloga se spremeni samo po potrjenem prevzemu.</div>${orders.length?`<div class="gm-ss-list">${orders.map(o=>`<article class="gm-ss-card"><div><h3>#${o.purchase_order_id} · ${esc(o.crop)} ${esc(o.variety||"")}</h3><div class="gm-ss-meta">${esc(o.supplier)} · naročeno ${o.ordered_quantity} ${esc(o.unit)} · ${money(o.total_eur)} · ${esc(o.order_date)}</div></div><div class="gm-ss-actions">${o.source_url?`<a href="${esc(o.source_url)}" target="_blank" rel="noopener noreferrer">PONUDBA</a>`:""}<button type="button" data-receive-order="${o.purchase_order_id}">PREVZEM SEMENA</button></div></article>`).join("")}</div>`:'<div class="gm-ss-empty">Ni odprtih semenskih naročil.</div>'}`;
}

function renderReceive(){
  const o=state.receiveOrder;
  content.innerHTML=`<form id="gm-ss-receive-form" class="gm-ss-receive-form"><h3>PREVZEM SEMENA · naročilo #${o.purchase_order_id}</h3><p>${esc(o.crop)} ${esc(o.variety||"")} · ${esc(o.supplier)}</p><div class="gm-ss-warning">Vpiši dejansko količino iz paketa. Šele ta potrditev poveča fizično zalogo in ustvari Seed Inventory lot.</div><label>Datum prevzema<input name="received_on" type="date" value="${today()}" required></label><label>Dejansko prejeta količina<input name="received_quantity" type="number" min="0.001" step="0.001" value="${o.ordered_quantity}" required></label><label>Lot številka<input name="lot_number" placeholder="z embalaže"></label><label>Velikost paketa<input name="package_size" type="number" min="0.001" step="0.001"></label><label>TKW/TSW g/1000<input name="thousand_seed_weight_g" type="number" min="0.001" step="0.001"></label><label>Kalivost %<input name="germination_pct" type="number" min="1" max="100" value="95"></label><label>Vznik %<input name="field_emergence_pct" type="number" min="1" max="100" value="90"></label><label>Rok uporabe<input name="expiry_date" type="date"></label><button class="gm-ss-action" type="submit">POTRDI PREVZEM IN DODAJ V ZALOGO</button><button class="gm-ss-action secondary" type="button" data-cancel-receive>NAZAJ</button></form>`;
}

async function runSearch(crop,variety="",options={}){
  state.loading=true;state.error="";state.notice="";state.selectedOffer=null;state.openOrders=null;state.receiveOrder=null;render();
  try{
    const params=new URLSearchParams({crop,eu_only:String(options.euOnly??true),refresh:String(options.refresh??false)});
    if(variety)params.set("variety",variety);
    state.data=await apiRequest(`/api/seed-suppliers/search?${params.toString()}`);
  }catch(error){state.error=error?.message||"Spletno iskanje ni uspelo.";state.data=null;}
  state.loading=false;render();
}

async function loadOpenOrders(){
  state.loading=true;state.error="";state.selectedOffer=null;state.receiveOrder=null;render();
  try{state.openOrders=await apiRequest("/api/seed-inventory/purchase-orders/open");}
  catch(error){state.error=error?.message||"Odprtih naročil ni mogoče naložiti.";state.openOrders=null;}
  state.loading=false;render();
}

async function open(crop="",variety=""){
  root.classList.add("open");state.open=true;state.error="";
  try{
    await loadCatalog();renderCropOptions(crop||"");renderVarietyOptions(variety||"");
    if(crop)runSearch(crop,variety,{euOnly:form.elements.eu_only.checked});
  }catch(error){state.error=error?.message||"Seznama kultur in sort ni mogoče naložiti.";render();}
}
function close(){root.classList.remove("open");state.open=false;}

function installPlantDbButtons(){
  document.querySelectorAll(".crop-catalog-card .variety-list > span").forEach((item)=>{
    if(item.querySelector(".gm-ss-inline"))return;
    const crop=item.closest(".crop-catalog-card")?.querySelector("h3")?.textContent?.trim();
    const variety=item.querySelector(":scope > strong")?.textContent?.trim();
    if(!crop||!variety)return;
    const button=document.createElement("button");button.type="button";button.className="gm-ss-inline";button.textContent="KJE KUPITI SEME";button.dataset.crop=crop;button.dataset.variety=variety;item.appendChild(button);
  });
}

new MutationObserver(installPlantDbButtons).observe(document.body,{childList:true,subtree:true});
installPlantDbButtons();

document.addEventListener("click",e=>{const b=e.target.closest(".gm-ss-inline");if(b)open(b.dataset.crop||"",b.dataset.variety||"");});
document.getElementById("gm-seed-web-btn").addEventListener("click",()=>open());
document.getElementById("gm-ss-open-orders").addEventListener("click",loadOpenOrders);
document.querySelector(".gm-ss-close").addEventListener("click",close);
root.addEventListener("click",e=>{if(e.target===root)close();});
form.elements.crop.addEventListener("change",()=>renderVarietyOptions());
form.addEventListener("submit",e=>{e.preventDefault();const fd=new FormData(form);runSearch(String(fd.get("crop")||"").trim(),String(fd.get("variety")||"").trim(),{euOnly:fd.get("eu_only")==="on",refresh:fd.get("refresh")==="on"});});

content.addEventListener("click",e=>{
  const offerButton=e.target.closest("[data-order-offer]");
  if(offerButton){state.selectedOffer=JSON.parse(decodeURIComponent(offerButton.dataset.orderOffer));state.openOrders=null;render();return;}
  if(e.target.closest("[data-cancel-order]")){state.selectedOffer=null;render();return;}
  if(e.target.closest("[data-cancel-receive]")){state.receiveOrder=null;renderOpenOrders();return;}
  const receiveButton=e.target.closest("[data-receive-order]");
  if(receiveButton){state.receiveOrder=(state.openOrders?.orders||[]).find(o=>String(o.purchase_order_id)===String(receiveButton.dataset.receiveOrder))||null;render();}
});

content.addEventListener("submit",async e=>{
  if(e.target.id==="gm-ss-order-form"){
    e.preventDefault();const fd=new FormData(e.target);const o=state.selectedOffer;
    state.loading=true;render();
    try{
      const quantity=Number(fd.get("quantity"));const total=Number(fd.get("total_price_eur"));
      const result=await apiRequest("/api/seed-inventory/purchase-orders/from-offer",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({supplier_name:o.supplier,crop:o.crop,variety:o.variety||null,quantity,unit:String(fd.get("unit")),total_price_eur:total,source_url:o.url,offer_title:o.title,expected_date:fd.get("expected_date")||null})});
      state.notice=`Naročilo #${result.purchase_order_id} je ustvarjeno. Seme še ni na zalogi.`;state.selectedOffer=null;state.loading=false;await loadOpenOrders();
    }catch(error){state.loading=false;state.error=error?.message||"Naročila ni mogoče ustvariti.";render();}
    return;
  }
  if(e.target.id==="gm-ss-receive-form"){
    e.preventDefault();const fd=new FormData(e.target);const o=state.receiveOrder;state.loading=true;render();
    const optionalNumber=(name)=>{const value=String(fd.get(name)||"").trim();return value?Number(value):null;};
    try{
      const result=await apiRequest(`/api/seed-inventory/purchase-orders/${o.purchase_order_id}/receive`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({received_on:fd.get("received_on"),received_quantity:Number(fd.get("received_quantity")),lot_number:fd.get("lot_number")||null,package_size:optionalNumber("package_size"),thousand_seed_weight_g:optionalNumber("thousand_seed_weight_g"),germination_pct:Number(fd.get("germination_pct")),field_emergence_pct:Number(fd.get("field_emergence_pct")),expiry_date:fd.get("expiry_date")||null})});
      state.notice=`Prevzem potrjen: ${result.received_quantity} ${result.unit} je dodano v Seed Inventory.`;state.receiveOrder=null;state.loading=false;window.dispatchEvent(new CustomEvent("growmaster:seed-inventory-changed",{detail:result}));await loadOpenOrders();
    }catch(error){state.loading=false;state.error=error?.message||"Prevzema ni mogoče potrditi.";render();}
  }
});

window.GrowMasterSeedSearch={open,search:runSearch,openOrders:loadOpenOrders};
window.addEventListener("growmaster:search-seed",e=>open(e.detail?.crop||"",e.detail?.variety||""));