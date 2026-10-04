import React, {useEffect, useRef, useState} from "react";
import {apiRequest} from "./platform";

const cropEmpty={kc_initial:"",kc_mid:"",kc_late:"",root_depth_m:"",depletion_fraction:"",source:""};
const bedEmpty={field_capacity_pct:"",wilting_point_pct:"",efficiency_pct:"",flow_l_min:"",max_application_mm:"",sensor_dry_pct:"",sensor_wet_pct:"",source:"",opensprinkler_station_entity:null,max_run_seconds:3600};
const localDay=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;};
const dayEmpty={day:localDay(),stage:"mid",initial_depletion_mm:"",eto_mm:"",effective_rain_mm:"",applied_irrigation_mm:"",weather_source:"",soil_moisture_pct:"",sensor_observed_at:""};
const statusNames={missing_data:"Manjkajo podatki",review:"Potreben pregled",irrigate:"Predlagano zalivanje",hold:"Brez predlaganega zalivanja"};

export function IrrigationPlanner({crops,beds}) {
  const [profiles,setProfiles]=useState({crops:[],beds:[]}),[cropId,setCropId]=useState(""),[bedId,setBedId]=useState("");
  const [cp,setCp]=useState(cropEmpty),[bp,setBp]=useState(bedEmpty),[day,setDay]=useState(dayEmpty);
  const [report,setReport]=useState(null),[saved,setSaved]=useState([]),[error,setError]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
  const generation=useRef(0);
  const [osPreview,setOsPreview]=useState(null),[osBusy,setOsBusy]=useState(false);
  const osGeneration=useRef(0);
  useEffect(()=>{let closed=false; apiRequest("/api/irrigation/profiles").then(p=>{if(!closed)setProfiles(p);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;generation.current++;};},[]);
  useEffect(()=>{setCp(profiles.crops.find(p=>String(p.crop_id)===cropId)||cropEmpty);},[cropId,profiles]);
  useEffect(()=>{setBp({...bedEmpty,...profiles.beds.find(p=>String(p.bed_id)===bedId)});},[bedId,profiles]);
  useEffect(()=>{generation.current++;setReport(null);setMessage("");setBusy(false);},[cropId,bedId,cp,bp,day]);
  useEffect(()=>{let closed=false;setSaved([]);apiRequest(`/api/irrigation/daily?day=${day.day}`).then(r=>{if(!closed)setSaved(r.rows);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[day.day]);
  useEffect(()=>{osGeneration.current++;setOsPreview(null);setOsBusy(false);return()=>{osGeneration.current++;};},[profiles,saved,day,cp,bp,cropId,bedId]);
  function numeric(form) {return Object.fromEntries(Object.entries(form).filter(([k])=>!["crop_id","bed_id"].includes(k)).map(([k,v])=>[k,k==="source"?v:k==="opensprinkler_station_entity"?v||null:v===""||v==null?null:Number(v)]));}
  async function prepareOpenSprinkler() {
    const n=++osGeneration.current;setOsBusy(true);setOsPreview(null);setError("");
    try {const r=await apiRequest(`/api/irrigation/opensprinkler?day=${day.day}`);if(n===osGeneration.current)setOsPreview(r);}
    catch(e){if(n===osGeneration.current)setError(e.message);}finally{if(n===osGeneration.current)setOsBusy(false);}
  }
  async function saveProfile(kind) {
    const n=++generation.current;setBusy(true);setError("");setReport(null);
    try {const payload=numeric(kind==="crops"?cp:bp);await apiRequest(`/api/irrigation/${kind}/${kind==="crops"?cropId:bedId}`,{method:"PUT",body:JSON.stringify(payload)});
      const p=await apiRequest("/api/irrigation/profiles");if(n===generation.current){setProfiles(p);setMessage("Profil je shranjen.");}
    } catch(e){if(n===generation.current)setError(e.message);}finally{if(n===generation.current)setBusy(false);}
  }
  async function calculate(save=false) {
    const n=++generation.current;setBusy(true);setError("");setReport(null);setMessage("");
    try {
      const payload={bed_id:Number(bedId),crop_id:Number(cropId),day:day.day,stage:day.stage,weather_source:day.weather_source,
        ...Object.fromEntries(["initial_depletion_mm","eto_mm","effective_rain_mm","applied_irrigation_mm","soil_moisture_pct"].map(k=>[k,day[k]===""?null:Number(day[k])])),
        sensor_observed_at:day.sensor_observed_at?new Date(day.sensor_observed_at).toISOString():null};
      const r=await apiRequest(save?"/api/irrigation/daily":"/api/irrigation/calculate",{method:save?"PUT":"POST",body:JSON.stringify(payload)});
      if(n===generation.current){setReport(r);if(save){setSaved(s=>[...s.filter(x=>x.bed_id!==r.bed_id),r]);setMessage("Dnevni izračun je shranjen; morebitni prejšnji izračun iste grede in dneva je nadomeščen.");}}
    }catch(e){if(n===generation.current)setError(e.message);}finally{if(n===generation.current)setBusy(false);}
  }
  function field(form,setter,key,label,min,max,optional=false) {return <label key={key}>{label}<input type="number" step="any" min={min} max={max} required={!optional} value={form[key]??""} onChange={e=>setter({...form,[key]:e.target.value})}/></label>;}
  const storedCrop=profiles.crops.find(p=>String(p.crop_id)===cropId),storedBed=profiles.beds.find(p=>String(p.bed_id)===bedId);
  const dirty=JSON.stringify(numeric(cp))!==JSON.stringify(numeric(storedCrop||cropEmpty))||JSON.stringify(numeric(bp))!==JSON.stringify(numeric({...bedEmpty,...storedBed}));
  return <section className="panel" aria-label="Namakanje">
    <p className="eyebrow">Dnevna vodna bilanca</p><h2>Namakanje</h2>
    <p>Začetna različica z ročnimi podatki. Vremenska postaja, WH52 in Home Assistant še niso samodejno povezani. Izberi kulturo in gredico; fazo in začetni primanjkljaj potrdi sam. Izbira kulture ne preverja dejanske zasaditve.</p>
    <div className="range-form"><label>Kultura za namakanje<select value={cropId} onChange={e=>setCropId(e.target.value)}><option value="">Izberi kulturo</option>{crops.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label>Gredica za namakanje<select value={bedId} onChange={e=>setBedId(e.target.value)}><option value="">Izberi gredico</option>{beds.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label></div>
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    <details><summary>Profil kulture — koeficienti in korenine</summary>
      <p>Vnesi preverjene koeficiente za svojo kulturo in način pridelave. Globina je trenutna učinkovita globina korenin, ne največja globina odrasle rastline. Delež izsušitve je med 0 in 1.</p>
      <form className="planning-form" onSubmit={e=>{e.preventDefault();saveProfile("crops");}}>
        {field(cp,setCp,"kc_initial","Kc — začetna faza",0,2)}{field(cp,setCp,"kc_mid","Kc — polna rast",0,2)}{field(cp,setCp,"kc_late","Kc — pozna faza",0,2)}
        {field(cp,setCp,"root_depth_m","Učinkovita globina korenin (m)",0.001,3)}{field(cp,setCp,"depletion_fraction","Dovoljeni delež izsušitve",0.001,0.999)}
        <label>Vir profila kulture<input required maxLength={500} value={cp.source} onChange={e=>setCp({...cp,source:e.target.value})}/></label>
        <button className="secondary-button" disabled={!cropId||busy}>SHRANI PROFIL KULTURE</button>
      </form></details>
    <details><summary>Profil grede — tla, pretok in WH52</summary>
      <p>Poljska kapaciteta in točka venenja sta volumenska deleža vode v tleh, ne odstotka WH52. Pretok naj velja samo za izbrano gredico. Skupnih ventilov ali con ta različica ne sešteva.</p>
      <form className="planning-form" onSubmit={e=>{e.preventDefault();saveProfile("beds");}}>
        {field(bp,setBp,"field_capacity_pct","Poljska kapaciteta (% vol.)",0.001,70)}{field(bp,setBp,"wilting_point_pct","Točka venenja (% vol.)",0,69.999)}
        {field(bp,setBp,"efficiency_pct","Učinkovitost namakanja (%)",0.001,100)}{field(bp,setBp,"flow_l_min","Pretok grede (l/min)",0.001,10000,true)}
        {field(bp,setBp,"max_application_mm","Največji enkratni odmerek (mm)",0.001,100)}{field(bp,setBp,"sensor_dry_pct","Umerjeni suhi prag WH52 (%)",0,100,true)}{field(bp,setBp,"sensor_wet_pct","Umerjeni mokri prag WH52 (%)",0,100,true)}
        <label>Vir profila tal in umerjanja<input required maxLength={500} value={bp.source} onChange={e=>setBp({...bp,source:e.target.value})}/></label>
        <label>Postaja OpenSprinkler v Home Assistantu<input placeholder="switch.greda_1_station_enabled" pattern="switch\.[a-z0-9_]+" maxLength={150} value={bp.opensprinkler_station_entity||""} onChange={e=>setBp({...bp,opensprinkler_station_entity:e.target.value})}/></label>
        {field(bp,setBp,"max_run_seconds","Največji čas postaje (sekunde)",1,86400)}
        <p>Ena postaja lahko predstavlja samo eno gredico. Vnesi entity ID stikala postaje iz Home Assistanta; GrowMaster njegovega obstoja še ne preverja.</p>
        <button className="secondary-button" disabled={!bedId||busy}>SHRANI PROFIL GREDE</button>
      </form></details>
    <h3>Dnevni izračun</h3><p>ET₀ je referenčna evapotranspiracija v mm/dan, ne samo izhlapevanje. Učinkoviti dež je voda, ki doseže korenine; pod streho ni enak dežju na postaji. Izvedeno zalivanje vnesi kot dejanski bruto odmerek v mm.</p>
    {dirty&&<p>Spremembe profilov najprej shrani. Izračun uporablja shranjene profile.</p>}
    <form className="planning-form" onSubmit={e=>{e.preventDefault();calculate(e.nativeEvent.submitter?.value==="save");}}>
      <label>Dan bilance<input type="date" required max={localDay()} value={day.day} onChange={e=>setDay({...day,day:e.target.value})}/></label>
      <label>Faza rasti<select value={day.stage} onChange={e=>setDay({...day,stage:e.target.value})}><option value="initial">Začetna</option><option value="mid">Polna rast</option><option value="late">Pozna</option></select></label>
      {field(day,setDay,"initial_depletion_mm","Začetni primanjkljaj (mm)",0,2100)}{field(day,setDay,"eto_mm","ET₀ (mm/dan)",0,30,true)}
      {field(day,setDay,"effective_rain_mm","Učinkoviti dež (mm)",0,500)}{field(day,setDay,"applied_irrigation_mm","Že izvedeno zalivanje (mm)",0,100)}
      <label>Vir dnevnih podatkov<input required maxLength={500} value={day.weather_source} onChange={e=>setDay({...day,weather_source:e.target.value})}/></label>
      {field(day,setDay,"soil_moisture_pct","WH52 — vlaga (%)",0,100,true)}<label>Čas meritve WH52 (lokalni čas)<input type="datetime-local" value={day.sensor_observed_at} onChange={e=>setDay({...day,sensor_observed_at:e.target.value})}/></label>
      <button className="primary-button" disabled={!bedId||!cropId||busy||dirty}>IZRAČUNAJ NAMAKANJE</button>
      <button className="secondary-button" value="save" disabled={!bedId||!cropId||busy||dirty}>IZRAČUNAJ IN SHRANI DAN</button>
    </form>
    {report&&<article aria-label="Rezultat namakanja"><h3>{statusNames[report.status]}</h3><p>{report.day} · {report.crop} · gredica {report.bed} · zanesljivost: nizka (ročna ocena)</p>
      {report.etc_mm!=null&&<p>Poraba ETc: {report.etc_mm} mm · primanjkljaj: {report.depletion_mm} mm · prag zalivanja: {report.raw_mm} mm</p>}
      {report.litres!=null&&<p>Predlagani bruto odmerek: <strong>{report.gross_mm} mm · {report.litres} l</strong> · {report.minutes==null?"čas ni določen":`${report.minutes} min pri vnesenem pretoku`}</p>}
      <ul>{report.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul><small>{report.note}</small></article>}
    <details><summary>Shranjeni izračuni za {day.day} ({saved.length})</summary><p>To so posnetki izračuna s takratnimi profili, ne dokazi izvedenega zalivanja. Sprememba profila jih ne preračuna.</p><ul>{saved.map(r=><li key={r.bed_id}>{r.crop} · gredica {r.bed}: {statusNames[r.status]} · {r.litres==null?"količina ni določena":`${r.litres} l`} · {r.day}</li>)}</ul></details>
    <h3>OpenSprinkler prek Home Assistanta</h3>
    <p>Pripravi osnutke iz shranjenih današnjih izračunov, največ šest ur starih. Pred tem shrani povezavo postaje in ponovno izračunaj dan. To ni samodejni zagon ventilov.</p>
    <button type="button" className="secondary-button" disabled={dirty||busy||osBusy} onClick={prepareOpenSprinkler}>PRIPRAVI AKCIJE OPENSPRINKLER</button>
    {osPreview&&<div aria-label="Osnutki OpenSprinkler"><p>{osPreview.note}</p>{!osPreview.rows.length&&<p>Za izbrani dan ni shranjenih izračunov.</p>}
      {osPreview.rows.map(r=><article key={r.bed_id}><strong>Gredica {r.bed||r.bed_id} · {r.status==="draft"?"Osnutek za ročni pregled":"Akcija ni pripravljena"}</strong>
        {r.status==="draft"?<><p>{r.litres} l · {r.run_seconds} sekund · {r.action.target.entity_id}</p><ul>{r.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul><p>Spodnji zapis lahko po preverjanju uporabiš v Home Assistantu, Orodja za razvijalce → Akcije → YAML. Izvedba tam dejansko odpre ventil.</p><textarea aria-label={`Akcija OpenSprinkler za gredico ${r.bed||r.bed_id}`} readOnly rows={8} value={r.yaml}/></>:<ul>{r.reasons.map((w,i)=><li key={i}>{w}</li>)}</ul>}
      </article>)}</div>}
    <small>ETc = ET₀ × Kc. Voda v koreninah je ocenjena iz poljske kapacitete, točke venenja in globine korenin. Izračun ne modelira kapilarnega dotoka, odtoka ali rasti korenin. Podatkov ne pošilja Home Assistantu in ne odpira ventilov.</small>
  </section>;
}
