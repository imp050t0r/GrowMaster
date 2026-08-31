import { apiRequest } from "./platform";

const css = `
#gm-seed-web-btn{position:fixed;right:18px;bottom:132px;z-index:1189;border:0;border-radius:999px;background:#235a45;color:#fff;padding:12px 16px;font-weight:800;box-shadow:0 8px 28px #0003;cursor:pointer}
#gm-seed-web{position:fixed;inset:0;z-index:1310;background:#07110dcc;display:none;justify-content:flex-end;backdrop-filter:blur(3px)}
#gm-seed-web.open{display:flex}.gm-ss-shell{width:min(980px,100%);height:100%;overflow:auto;background:#f7f4ec;padding:20px;box-shadow:-12px 0 42px #0005}
.gm-ss-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.gm-ss-head h2{margin:0;color:#143c2f}.gm-ss-head p{margin:4px 0 0;color:#68645d}.gm-ss-close{border:0;background:transparent;font-size:28px;cursor:pointer}
.gm-ss-form{display:grid;grid-template-columns:1fr 1fr auto auto auto;gap:8px;margin:16px 0;align-items:end}.gm-ss-form label{display:grid;gap:4px;font-size:12px;font-weight:800}.gm-ss-form input{padding:10px;border:1px solid #c8c3b7;border-radius:9px;background:white}.gm-ss-check{display:flex!important;align-items:center;gap:6px;padding-bottom:10px}.gm-ss-search{padding:11px 14px;border:0;border-radius:9px;background:#143c2f;color:white;font-weight:900;cursor:pointer}.gm-ss-status{margin:8px 0 12px;color:#68645d}.gm-ss-error{background:#ffe1dc;color:#8c2b20;padding:10px;border-radius:10px}.gm-ss-list{display:grid;gap:9px}.gm-ss-card{background:white;border:1px solid #ded9cd;border-radius:14px;padding:13px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px}.gm-ss-card h3{margin:0 0 4px;color:#143c2f;font-size:17px}.gm-ss-meta,.gm-ss-snippet{font-size:12px;color:#68645d;line-height:1.4}.gm-ss-price{font-size:20px;font-weight:900;color:#143c2f;text-align:right}.gm-ss-actions{display:flex;gap:7px;justify-content:flex-end;align-items:center;margin-top:8px;flex-wrap:wrap}.gm-ss-actions a,.gm-ss-actions button{border:0;border-radius:8px;padding:8px 10px;font-weight:800;text-decoration:none;cursor:pointer}.gm-ss-actions a{background:#143c2f;color:white}.gm-ss-actions button{background:#e7e2d6;color:#143c2f}.gm-ss-badge{display:inline-block;padding:2px 7px;border-radius:999px;background:#e7e2d6;margin-right:5px;font-size:11px;font-weight:800}.gm-ss-empty{padding:26px;text-align:center;background:white;border:1px dashed #cfc9bd;border-radius:14px;color:#68645d}
@media(max-width:760px){.gm-ss-shell{padding:14px}.gm-ss-form{grid-template-columns:1fr}.gm-ss-check{padding:4px 0}.gm-ss-card{grid-template-columns:1fr}.gm-ss-price{text-align:left}#gm-seed-web-btn{right:12px;bottom:122px}}
`;

function esc(value){return String(value??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));}
function money(value){return value==null?"cena ni zaznana":`${Number(value).toLocaleString("sl-SI",{minimumFractionDigits:2,maximumFractionDigits:2})} €`;}

const state={open:false,loading:false,error:"",data:null};

document.head.insertAdjacentHTML("beforeend",`<style>${css}</style>`);
document.body.insertAdjacentHTML("beforeend",`
<button id="gm-seed-web-btn" type="button">🌐 Seme online</button>
<aside id="gm-seed-web" role="dialog" aria-modal="true" aria-label="Spletno iskanje semen">
  <div class="gm-ss-shell">
    <div class="gm-ss-head"><div><h2>Dobavitelji semen</h2><p>GrowMaster v živo preveri spletne ponudbe in jih primerja za izbrano kulturo ali sorto.</p></div><button class="gm-ss-close" type="button" aria-label="Zapri">×</button></div>
    <form class="gm-ss-form" id="gm-ss-form">
      <label>Kultura<input name="crop" required minlength="2" placeholder="npr. Koriander"></label>
      <label>Sorta<input name="variety" placeholder="npr. Calypso"></label>
      <label class="gm-ss-check"><input type="checkbox" name="eu_only" checked> samo EU</label>
      <label class="gm-ss-check"><input type="checkbox" name="refresh"> sveži podatki</label>
      <button class="gm-ss-search" type="submit">POIŠČI</button>
    </form>
    <div id="gm-ss-content"><div class="gm-ss-empty">Vpiši rastlino ali sorto in GrowMaster bo preveril internet.</div></div>
  </div>
</aside>`);

const root=document.getElementById("gm-seed-web");
const form=document.getElementById("gm-ss-form");
const content=document.getElementById("gm-ss-content");

function render(){
  if(state.loading){content.innerHTML='<div class="gm-ss-status">Preverjam spletne dobavitelje …</div>';return;}
  if(state.error){content.innerHTML=`<div class="gm-ss-error">${esc(state.error)}</div>`;return;}
  if(!state.data)return;
  const d=state.data;
  const status=`Preverjeno ${esc(d.checked_at||"")} · ${d.offer_count||0} zadetkov pri ${d.supplier_count||0} dobaviteljih${d.cached?" · predpomnjeno":" · sveže z interneta"}`;
  const cards=(d.offers||[]).map((o)=>`<article class="gm-ss-card"><div><h3>${esc(o.title)}</h3><div class="gm-ss-meta"><span class="gm-ss-badge">${esc(o.supplier)}</span><span class="gm-ss-badge">${esc(o.country)}</span>${o.eu?'<span class="gm-ss-badge">EU</span>':''}</div><p class="gm-ss-snippet">${esc(o.snippet||"")}</p></div><div><div class="gm-ss-price">${esc(money(o.price_eur))}</div><div class="gm-ss-actions"><button type="button" data-copy-offer="${encodeURIComponent(JSON.stringify({supplier:o.supplier,title:o.title,url:o.url,price_eur:o.price_eur,crop:d.crop,variety:d.variety}))}">V NABAVO</button><a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">ODPRI</a></div></div></article>`).join("");
  content.innerHTML=`<div class="gm-ss-status">${status}</div>${d.note?`<div class="gm-ss-status">${esc(d.note)}</div>`:""}${cards||'<div class="gm-ss-empty">Ni najdenih ustreznih ponudb. Poskusi brez sorte ali brez filtra EU.</div>'}`;
}

async function runSearch(crop,variety="",options={}){
  state.loading=true;state.error="";render();
  try{
    const params=new URLSearchParams({crop,eu_only:String(options.euOnly??true),refresh:String(options.refresh??false)});
    if(variety)params.set("variety",variety);
    state.data=await apiRequest(`/api/seed-suppliers/search?${params.toString()}`);
  }catch(error){state.error=error?.message||"Spletno iskanje ni uspelo.";state.data=null;}
  state.loading=false;render();
}

function open(crop="",variety=""){
  root.classList.add("open");state.open=true;
  form.elements.crop.value=crop||"";form.elements.variety.value=variety||"";
  if(crop)runSearch(crop,variety,{euOnly:form.elements.eu_only.checked});
}
function close(){root.classList.remove("open");state.open=false;}

document.getElementById("gm-seed-web-btn").addEventListener("click",()=>open());
document.querySelector(".gm-ss-close").addEventListener("click",close);
root.addEventListener("click",e=>{if(e.target===root)close();});
form.addEventListener("submit",e=>{e.preventDefault();const fd=new FormData(form);runSearch(String(fd.get("crop")||"").trim(),String(fd.get("variety")||"").trim(),{euOnly:fd.get("eu_only")==="on",refresh:fd.get("refresh")==="on"});});
content.addEventListener("click",e=>{
  const button=e.target.closest("[data-copy-offer]");if(!button)return;
  const offer=JSON.parse(decodeURIComponent(button.dataset.copyOffer));
  window.dispatchEvent(new CustomEvent("growmaster:seed-offer-selected",{detail:offer}));
  button.textContent="IZBRANO";
});

window.GrowMasterSeedSearch={open,search:runSearch};
window.addEventListener("growmaster:search-seed",e=>open(e.detail?.crop||"",e.detail?.variety||""));
