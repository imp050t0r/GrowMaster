import React, {useEffect, useRef, useState} from "react";
import {apiRequest} from "./platform";
import {cropIdForBed,dailyBedStates} from "./irrigationPlanner";

const cropEmpty={kc_initial:"",kc_mid:"",kc_late:"",root_depth_m:"",depletion_fraction:"",source:""};
const bedEmpty={mode:"smart_irrigation",irrigation_zone:"",wh51_group:null,field_capacity_pct:"",wilting_point_pct:"",efficiency_pct:"",flow_l_min:"",max_application_mm:"",sensor_dry_pct:"",sensor_wet_pct:"",source:"",opensprinkler_station_entity:null,smart_irrigation_entity:null,max_run_seconds:3600};
const localDay=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;};
const dayEmpty={day:localDay(),stage:"mid",initial_depletion_mm:"",eto_mm:"",effective_rain_mm:"",applied_irrigation_mm:"",weather_source:"",soil_moisture_pct:"",sensor_observed_at:""};
const statusNames={missing_data:"Manjkajo podatki",review:"Potreben pregled",irrigate:"Predlagano zalivanje",hold:"Brez predlaganega zalivanja"};

export function IrrigationPlanner({crops,beds}) {
  const [profiles,setProfiles]=useState({crops:[],beds:[]}),[cropId,setCropId]=useState(""),[bedId,setBedId]=useState("");
  const [sensorGroups,setSensorGroups]=useState(Array.from({length:16},(_,i)=>({group_number:i+1,name:`WH51 ${i+1}`,entity_id:""})));
  const [cp,setCp]=useState(cropEmpty),[bp,setBp]=useState(bedEmpty),[day,setDay]=useState(dayEmpty);
  const [report,setReport]=useState(null),[saved,setSaved]=useState([]),[error,setError]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
  const [readiness,setReadiness]=useState(null);
  const [ledger,setLedger]=useState([]),[ledgerOpening,setLedgerOpening]=useState(""),[ledgerRain,setLedgerRain]=useState("0"),[ledgerApplied,setLedgerApplied]=useState("0"),[ledgerSource,setLedgerSource]=useState("Ročni pregled"),[ledgerBusy,setLedgerBusy]=useState(false);
  const generation=useRef(0);
  const [osPreview,setOsPreview]=useState(null),[osBusy,setOsBusy]=useState(false);
  const osGeneration=useRef(0);
  const [siPreview,setSiPreview]=useState(null),[siBusy,setSiBusy]=useState(false);
  const siGeneration=useRef(0);
  const [haStatus,setHaStatus]=useState(null),[haBusy,setHaBusy]=useState(false);
  const [haStates,setHaStates]=useState(null);
  function chooseBed(value) {
    setBedId(value);
    const bed=beds.find(item=>String(item.id)===String(value));
    setCropId(cropIdForBed(bed,crops));
  }
  useEffect(()=>{let closed=false; apiRequest("/api/irrigation/profiles").then(p=>{if(!closed){setProfiles(p);setSensorGroups(Array.from({length:16},(_,i)=>p.sensor_groups?.find(item=>item.group_number===i+1)||{group_number:i+1,name:`WH51 ${i+1}`,entity_id:""}));}}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;generation.current++;};},[]);
  useEffect(()=>{let closed=false;apiRequest("/api/irrigation/home-assistant/status").then(r=>{if(!closed)setHaStatus(r);}).catch(()=>{if(!closed)setHaStatus({configured:false});});return()=>{closed=true;};},[]);
  useEffect(()=>{setCp(profiles.crops.find(p=>String(p.crop_id)===cropId)||cropEmpty);},[cropId,profiles]);
  useEffect(()=>{setBp({...bedEmpty,...profiles.beds.find(p=>String(p.bed_id)===bedId)});},[bedId,profiles]);
  useEffect(()=>{generation.current++;setReport(null);setMessage("");setBusy(false);},[cropId,bedId,cp,bp,day]);
  useEffect(()=>{let closed=false;setSaved([]);apiRequest(`/api/irrigation/daily?day=${day.day}`).then(r=>{if(!closed)setSaved(r.rows);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[day.day]);
  useEffect(()=>{let closed=false;setReadiness(null);apiRequest(`/api/irrigation/daily-readiness?day=${day.day}`).then(r=>{if(!closed)setReadiness(r);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[day.day,saved,beds,profiles]);
  useEffect(()=>{let closed=false;setLedger([]);setLedgerOpening("");setLedgerRain("0");setLedgerApplied("0");if(!bedId)return()=>{closed=true;};apiRequest(`/api/irrigation/water-ledger?bed_id=${bedId}&through=${day.day}`).then(r=>{if(!closed){const rows=r.rows||[];setLedger(rows);const current=rows.find(item=>item.day===day.day);const previous=rows.at(-1);const opening=current?.opening_depletion_mm??previous?.closing_depletion_mm;if(opening!=null){setLedgerOpening(String(opening));setDay(value=>({...value,initial_depletion_mm:String(opening)}));}if(current){setLedgerRain(String(current.effective_rain_mm));setLedgerApplied(String(current.applied_irrigation_mm));}}}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[bedId,day.day]);
  useEffect(()=>{osGeneration.current++;setOsPreview(null);setOsBusy(false);siGeneration.current++;setSiPreview(null);setSiBusy(false);return()=>{osGeneration.current++;siGeneration.current++;};},[profiles,saved,day,cp,bp,cropId,bedId]);
  function numeric(form) {return Object.fromEntries(Object.entries(form).filter(([k])=>!["crop_id","bed_id"].includes(k)).map(([k,v])=>[k,["mode","source","irrigation_zone"].includes(k)?v||null:["opensprinkler_station_entity","smart_irrigation_entity"].includes(k)?v||null:v===""||v==null?null:Number(v)]));}
  async function prepareOpenSprinkler() {
    const n=++osGeneration.current;setOsBusy(true);setOsPreview(null);setError("");
    try {const r=await apiRequest(`/api/irrigation/opensprinkler?day=${day.day}`);if(n===osGeneration.current)setOsPreview(r);}
    catch(e){if(n===osGeneration.current)setError(e.message);}finally{if(n===osGeneration.current)setOsBusy(false);}
  }
  async function prepareSmartIrrigation() {
    const n=++siGeneration.current;setSiBusy(true);setSiPreview(null);setError("");
    try {const r=await apiRequest(`/api/irrigation/smart-irrigation?day=${day.day}`);if(n===siGeneration.current)setSiPreview(r);}
    catch(e){if(n===siGeneration.current)setError(e.message);}finally{if(n===siGeneration.current)setSiBusy(false);}
  }
  async function testHomeAssistant() {
    setHaBusy(true);setError("");setMessage("");
    try {const r=await apiRequest("/api/irrigation/home-assistant/test",{method:"POST"});setHaStatus({configured:true,connected:true});setMessage(`Povezava s Home Assistantom deluje (${r.message}).`);}
    catch(e){setError(e.message);}finally{setHaBusy(false);}
  }
  async function readHomeAssistantStates() {
    setHaBusy(true);setError("");setHaStates(null);
    try {const r=await apiRequest("/api/irrigation/home-assistant/states");setHaStates(r);}
    catch(e){setError(e.message);}finally{setHaBusy(false);}
  }
  async function sendSmartIrrigation() {
    setHaBusy(true);setError("");setMessage("");
    try {const r=await apiRequest(`/api/irrigation/home-assistant/smart-irrigation?day=${day.day}`,{method:"POST"});setMessage(`V Home Assistant poslanih ${r.sent.length} posodobitev Kc. Ventili niso bili zagnani.`);setSiPreview(null);}
    catch(e){setError(e.message);}finally{setHaBusy(false);}
  }
  async function saveLedger() {
    if(report?.etc_mm==null){setError("Najprej izračunaj in shrani dnevno bilanco.");return;}
    setLedgerBusy(true);setError("");setMessage("");
    try {const result=await apiRequest("/api/irrigation/water-ledger",{method:"PUT",body:JSON.stringify({bed_id:Number(bedId),day:day.day,opening_depletion_mm:Number(ledgerOpening),etc_mm:report.etc_mm,effective_rain_mm:Number(ledgerRain),applied_irrigation_mm:Number(ledgerApplied),source:ledgerSource})});setMessage(`Vodna bilanca shranjena. Končni primanjkljaj: ${result.closing_depletion_mm} mm.`);const rows=await apiRequest(`/api/irrigation/water-ledger?bed_id=${bedId}&through=${day.day}`);setLedger(rows.rows);}
    catch(e){setError(e.message);}finally{setLedgerBusy(false);}
  }
  async function saveProfile(kind) {
    const n=++generation.current;setBusy(true);setError("");setReport(null);
    try {const payload=numeric(kind==="crops"?cp:bp);await apiRequest(`/api/irrigation/${kind}/${kind==="crops"?cropId:bedId}`,{method:"PUT",body:JSON.stringify(payload)});
      const p=await apiRequest("/api/irrigation/profiles");if(n===generation.current){setProfiles(p);setMessage("Profil je shranjen.");}
    } catch(e){if(n===generation.current)setError(e.message);}finally{if(n===generation.current)setBusy(false);}
  }
  async function saveSensorGroup(group) {
    setBusy(true);setError("");setMessage("");
    try {await apiRequest(`/api/irrigation/sensor-groups/${group.group_number}`,{method:"PUT",body:JSON.stringify({name:group.name,entity_id:group.entity_id||null})});const p=await apiRequest("/api/irrigation/profiles");setProfiles(p);setSensorGroups(Array.from({length:16},(_,i)=>p.sensor_groups.find(item=>item.group_number===i+1)||{group_number:i+1,name:`WH51 ${i+1}`,entity_id:""}));setMessage(`WH51 skupina ${group.group_number} je shranjena.`);}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function calculate(save=false) {
    const n=++generation.current;setBusy(true);setError("");setReport(null);setMessage("");
    try {
      const selectedMode=storedBed?.mode||"smart_irrigation";
      const payload={bed_id:Number(bedId),crop_id:Number(cropId),day:day.day,stage:day.stage,weather_source:day.weather_source,
        ...Object.fromEntries(["initial_depletion_mm","eto_mm","effective_rain_mm","applied_irrigation_mm","soil_moisture_pct"].map(k=>[k,day[k]===""?null:Number(day[k])])),
        sensor_observed_at:day.sensor_observed_at?new Date(day.sensor_observed_at).toISOString():null};
      if(selectedMode==="soil_sensor"){payload.soil_moisture_pct=null;payload.sensor_observed_at=null;}
      const r=await apiRequest(save?"/api/irrigation/daily":"/api/irrigation/calculate",{method:save?"PUT":"POST",body:JSON.stringify(payload)});
      if(n===generation.current){setReport(r);if(save){setSaved(s=>[...s.filter(x=>x.bed_id!==r.bed_id),r]);setMessage("Dnevni izračun je shranjen; morebitni prejšnji izračun iste grede in dneva je nadomeščen.");}}
    }catch(e){if(n===generation.current)setError(e.message);}finally{if(n===generation.current)setBusy(false);}
  }
  function field(form,setter,key,label,min,max,optional=false) {return <label key={key}>{label}<input type="number" step="any" min={min} max={max} required={!optional} value={form[key]??""} onChange={e=>setter({...form,[key]:e.target.value})}/></label>;}
  const storedCrop=profiles.crops.find(p=>String(p.crop_id)===cropId),storedBed=profiles.beds.find(p=>String(p.bed_id)===bedId);
  const selectedBed=beds.find(item=>String(item.id)===bedId);
  const currentPlanting=selectedBed?.current_planting;
  const reportByBed=new Map(saved.map(item=>[item.bed_id,item]));
  const dailyStates=dailyBedStates(beds,crops,profiles,saved);
  const dirty=JSON.stringify(numeric(cp))!==JSON.stringify(numeric(storedCrop||cropEmpty))||JSON.stringify(numeric(bp))!==JSON.stringify(numeric({...bedEmpty,...storedBed}));
  return <section className="panel" aria-label="Namakanje">
    <p className="eyebrow">Dnevna vodna bilanca</p><h2>Namakanje</h2>
    <p>Dnevni pregled uporablja trenutno aktivno zasaditev na gredici. Kultura se ob izbiri gredice predizbere iz GrowMasterja; fazo rasti, začetni primanjkljaj in dnevne meritve še potrdiš ročno. Home Assistant senzorje lahko prebere in preveri njihovo svežino, vendar jih še ne pretvori samodejno v ET₀, dež ali odločitev za zalivanje.</p>
    <div className="irrigation-bed-review" aria-label={`Pregled gredic za ${day.day}`}>
      <div className="section-heading"><div><p className="eyebrow">Pregled za {day.day}</p><h3>Gredice z aktivnim posevkom</h3></div><span>{beds.filter(item=>item.current_planting).length} aktivnih</span></div>
      {dailyStates.length===0?<p className="empty-state">Ni zabeleženih aktivnih zasaditev na gredicah.</p>:dailyStates.map(({bed:b,report,hasCropProfile,hasBedProfile,needsCalculation})=>{
        const planting=b.current_planting;
        const mode=profiles.beds.find(item=>item.bed_id===b.id)?.mode||"smart_irrigation";
        return <article key={b.id} className={String(b.id)===bedId?"selected":""}>
          <div><strong>Gredica {b.name}</strong><span>{planting.crop}{planting.variety?` · ${planting.variety}`:""} · {b.area_m2} m²</span>
            <small>{mode==="soil_sensor"?"Z merjenjem vlage":"Brez talnega senzorja"} · profil kulture: {hasCropProfile?"nastavljen":"manjka"} · profil grede: {hasBedProfile?"nastavljen":"manjka"}</small>
          </div>
          <div className="irrigation-bed-status"><b>{report?statusNames[report.status]:"Še ni izračuna"}</b>{report?.litres!=null&&<span>{report.litres} l</span>}{needsCalculation&&<small>Potrebni so današnji podatki</small>}</div>
          <button type="button" className="secondary-button" onClick={()=>chooseBed(String(b.id))}>{String(b.id)===bedId?"IZBRANA":"PREGLEJ GREDICO"}</button>
        </article>;
      })}
    </div>
    {readiness&&<article aria-label="Dnevna pripravljenost namakanja"><h3>Dnevno preverjanje: {readiness.ready_beds}/{readiness.active_beds} gredic pripravljenih</h3>
      <p>{readiness.note}</p><ul>{readiness.rows.map(row=><li key={row.bed_id}><strong>{row.bed} · {row.crop}{row.variety?` (${row.variety})`:""}</strong> · {row.mode==="smart_irrigation"?`Smart Irrigation: ${row.smart_irrigation_seconds==null?"ni izračuna":`${row.smart_irrigation_seconds} sekund`} · ${row.decision==="irrigate"?"zalivanje priporočeno":row.decision==="hold"?"zalivanje ni potrebno":"pregled potreben"}`:`WH51 skupina ${row.wh51_group_name||row.wh51_group||"ni dodeljena"} · ${row.sensor_group_beds} gredic`} {!row.ready?` · ${row.reasons.join(" ")}`:" · pripravljeno"}{row.action&&<><p>Osnutek za ročni pregled: {row.action.target.entity_id} · {row.action.data.run_seconds} sekund</p><textarea aria-label={`Osnutek OpenSprinkler za gredico ${row.bed}`} readOnly rows={6} value={`action: opensprinkler.run_station\ntarget:\n  entity_id: ${row.action.target.entity_id}\ndata:\n  run_seconds: ${row.action.data.run_seconds}\n  queue_option: append`}/></>}</li>)}</ul></article>}
    <div className="range-form"><label>Kultura<select value={cropId} onChange={e=>setCropId(e.target.value)}><option value="">Izberi kulturo</option>{crops.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label>Gredica<select value={bedId} onChange={e=>chooseBed(e.target.value)}><option value="">Izberi gredico</option>{beds.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label></div>
    {currentPlanting&&<p className="irrigation-current-crop">Trenutna zasaditev GrowMasterja: <strong>{currentPlanting.crop} {currentPlanting.variety||""}</strong> · setev {currentPlanting.sowing_date}. Če je bila zasaditev v resnici že zamenjana, najprej posodobi evidenco setve.</p>}
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    <details><summary>Profil kulture — koeficienti in korenine</summary>
      <p>Vnesi preverjene koeficiente za svojo kulturo in način pridelave. Globina je trenutna učinkovita globina korenin, ne največja globina odrasle rastline. Delež izsušitve je med 0 in 1.</p>
      <form className="planning-form" onSubmit={e=>{e.preventDefault();saveProfile("crops");}}>
        {field(cp,setCp,"kc_initial","Kc — začetna faza",0,2)}{field(cp,setCp,"kc_mid","Kc — polna rast",0,2)}{field(cp,setCp,"kc_late","Kc — pozna faza",0,2)}
        {field(cp,setCp,"root_depth_m","Učinkovita globina korenin (m)",0.001,3)}{field(cp,setCp,"depletion_fraction","Dovoljeni delež izsušitve",0.001,0.999)}
        <label>Vir profila kulture<input required maxLength={500} value={cp.source} onChange={e=>setCp({...cp,source:e.target.value})}/></label>
        <button className="secondary-button" disabled={!cropId||busy}>SHRANI PROFIL KULTURE</button>
      </form></details>
    <details><summary>Profil grede — tla, pretok in WH51</summary>
      <p>Poljska kapaciteta in točka venenja sta volumenska deleža vode v tleh, ne odstotka WH52. Pretok naj velja samo za izbrano gredico. Skupnih ventilov ali con ta različica ne sešteva.</p>
      <form className="planning-form" onSubmit={e=>{e.preventDefault();saveProfile("beds");}}>
        <label>Način namakanja<select value={bp.mode||"smart_irrigation"} onChange={e=>setBp({...bp,mode:e.target.value})}><option value="soil_sensor">S senzorjem vlage v tleh</option><option value="smart_irrigation">Brez talnega senzorja — Smart Irrigation</option></select></label>
        {bp.mode==="soil_sensor"?<p>Način z merjenjem: za pripravljeno dnevno bilanco zahteva svež, povezan senzor tal. Njegova meritev preverja vodno bilanco.</p>:<p>Način brez talnega senzorja: Smart Irrigation vodi dnevno vremensko bilanco. GrowMaster potrebuje ET₀, dež in potrjeno začetno vodno stanje.</p>}
        <label>Namakalna cona (1–16)<select value={bp.irrigation_zone||""} onChange={e=>setBp({...bp,irrigation_zone:e.target.value})}><option value="">Izberi cono</option>{Array.from({length:16},(_,i)=><option key={i+1} value={`zone_${i+1}`}>Cona {i+1}</option>)}</select></label>
        {field(bp,setBp,"field_capacity_pct","Poljska kapaciteta (% vol.)",0.001,70)}{field(bp,setBp,"wilting_point_pct","Točka venenja (% vol.)",0,69.999)}
        {field(bp,setBp,"efficiency_pct","Učinkovitost namakanja (%)",0.001,100)}{field(bp,setBp,"flow_l_min","Pretok grede (l/min)",0.001,10000,true)}
        {field(bp,setBp,"max_application_mm","Največji enkratni odmerek (mm)",0.001,100)}{field(bp,setBp,"sensor_dry_pct","Umerjeni suhi prag WH51 (%)",0,100,true)}{field(bp,setBp,"sensor_wet_pct","Umerjeni mokri prag WH51 (%)",0,100,true)}
        <label>Vir profila tal in umerjanja<input required maxLength={500} value={bp.source} onChange={e=>setBp({...bp,source:e.target.value})}/></label>
        <label>Postaja OpenSprinkler v Home Assistantu<input placeholder="switch.greda_1_station_enabled" pattern="switch\.[a-z0-9_]+" maxLength={150} value={bp.opensprinkler_station_entity||""} onChange={e=>setBp({...bp,opensprinkler_station_entity:e.target.value})}/></label>
        <label>Smart Irrigation cona v Home Assistantu<input placeholder="sensor.smart_irrigation_greda_1" pattern="sensor\.smart_irrigation_[a-z0-9_]+" maxLength={150} value={bp.smart_irrigation_entity||""} onChange={e=>setBp({...bp,smart_irrigation_entity:e.target.value})}/></label>
        <label>Ročno dodeljena WH51 skupina<select value={bp.wh51_group||""} onChange={e=>setBp({...bp,wh51_group:e.target.value?Number(e.target.value):null})}><option value="">Brez WH51</option>{sensorGroups.map(group=><option key={group.group_number} value={group.group_number}>{group.group_number}. {group.name}{group.entity_id?" · senzor nastavljen":" · brez senzorja"}</option>)}</select></label>
        {field(bp,setBp,"max_run_seconds","Največji čas postaje (sekunde)",1,86400)}
        <p>Gredico ročno dodeli WH51 skupini; v isto skupino lahko dodaš poljubno število gredic. Dodelitev se ne spreminja samodejno. Entity ID senzorja nastavi enkrat v konfiguraciji skupin spodaj.</p>
        <button className="secondary-button" disabled={!bedId||busy}>SHRANI PROFIL GREDE</button>
      </form></details>
      <details><summary>WH51 skupine (največ 16)</summary><p>Vnesi HA entity ID enkrat na skupino. Potem v profilih ročno izberi, katere gredice ta senzor predstavlja.</p><div className="planning-form">{sensorGroups.map(group=><div className="range-form" key={group.group_number}><label>{group.group_number}. ime skupine<input maxLength={80} value={group.name} onChange={e=>setSensorGroups(current=>current.map(item=>item.group_number===group.group_number?{...item,name:e.target.value}:item))}/></label><label>WH51 entity ID<input placeholder={`sensor.wh51_${group.group_number}_soil_moisture`} pattern="sensor\.[a-z0-9_]+" maxLength={150} value={group.entity_id||""} onChange={e=>setSensorGroups(current=>current.map(item=>item.group_number===group.group_number?{...item,entity_id:e.target.value}:item))}/></label><button type="button" className="secondary-button" disabled={busy} onClick={()=>saveSensorGroup(group)}>SHRANI SKUPINO</button></div>)}</div></details>
    <h3>Dnevni izračun</h3><p>ET₀ je referenčna evapotranspiracija v mm/dan, ne samo izhlapevanje. Učinkoviti dež je voda, ki doseže korenine; pod streho ni enak dežju na postaji. Izvedeno zalivanje vnesi kot dejanski bruto odmerek v mm.</p>
    {dirty&&<p>Spremembe profilov najprej shrani. Izračun uporablja shranjene profile.</p>}
    <form className="planning-form" onSubmit={e=>{e.preventDefault();calculate(e.nativeEvent.submitter?.value==="save");}}>
      <label>Dan bilance<input type="date" required max={localDay()} value={day.day} onChange={e=>setDay({...day,day:e.target.value})}/></label>
      <label>Faza rasti<select value={day.stage} onChange={e=>setDay({...day,stage:e.target.value})}><option value="initial">Začetna</option><option value="mid">Polna rast</option><option value="late">Pozna</option></select></label>
      {field(day,setDay,"initial_depletion_mm","Začetni primanjkljaj (mm)",0,2100)}{field(day,setDay,"eto_mm","ET₀ (mm/dan)",0,30,true)}
      {field(day,setDay,"effective_rain_mm","Učinkoviti dež (mm)",0,500)}{field(day,setDay,"applied_irrigation_mm","Že izvedeno zalivanje (mm)",0,100)}
      <label>Vir dnevnih podatkov<input required maxLength={500} value={day.weather_source} onChange={e=>setDay({...day,weather_source:e.target.value})}/></label>
      {storedBed?.mode==="soil_sensor"?<p>Vlago bo GrowMaster prebral iz WH51 skupine {storedBed.wh51_group||"(še ni izbrana)"}.</p>:<>{field(day,setDay,"soil_moisture_pct","Vlaga v tleh (%)",0,100,true)}<label>Čas meritve tal (lokalni čas)<input type="datetime-local" value={day.sensor_observed_at} onChange={e=>setDay({...day,sensor_observed_at:e.target.value})}/></label></>}
      <button className="primary-button" disabled={!bedId||!cropId||busy||dirty}>IZRAČUNAJ NAMAKANJE</button>
      <button className="secondary-button" value="save" disabled={!bedId||!cropId||busy||dirty}>IZRAČUNAJ IN SHRANI DAN</button>
    </form>
    {report&&<article aria-label="Rezultat namakanja"><h3>{statusNames[report.status]}</h3><p>{report.day} · {report.crop} · gredica {report.bed} · zanesljivost: nizka (ročna ocena)</p>
      {report.etc_mm!=null&&<p>Poraba ETc: {report.etc_mm} mm · primanjkljaj: {report.depletion_mm} mm · prag zalivanja: {report.raw_mm} mm</p>}
      {report.litres!=null&&<p>Predlagani bruto odmerek: <strong>{report.gross_mm} mm · {report.litres} l</strong> · {report.minutes==null?"čas ni določen":`${report.minutes} min pri vnesenem pretoku`}</p>}
      <ul>{report.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul><small>{report.note}</small></article>}
    {bedId&&<details><summary>Večdnevna vodna bilanca · gredica {selectedBed?.name||bedId}</summary>
      <p>Začetni primanjkljaj se prenese iz zadnjega shranjenega dne. Dež in že izvedeno zalivanje preveri glede na meritve; te vrednosti se ne zajemajo samodejno.</p>
      <div className="planning-form"><label>Začetni primanjkljaj (mm)<input type="number" min="0" max="2100" step="any" value={ledgerOpening} onChange={e=>setLedgerOpening(e.target.value)} required/></label>
        <label>Učinkoviti dež danes (mm)<input type="number" min="0" max="500" step="any" value={ledgerRain} onChange={e=>setLedgerRain(e.target.value)}/></label>
        <label>Že izvedeno zalivanje danes (mm bruto)<input type="number" min="0" max="100" step="any" value={ledgerApplied} onChange={e=>setLedgerApplied(e.target.value)}/></label>
        <label>Vir potrditve<input maxLength="500" value={ledgerSource} onChange={e=>setLedgerSource(e.target.value)}/></label>
      </div>
      <button type="button" className="secondary-button" disabled={report?.etc_mm==null||ledgerBusy||!ledgerOpening} onClick={saveLedger}>SHRANI DNEVNO STANJE</button>
      {ledger.length>0?<ul>{ledger.map(item=><li key={item.day}>{item.day}: {item.opening_depletion_mm} mm + ETc {item.etc_mm} − dež {item.effective_rain_mm} − namakanje {item.applied_irrigation_mm} mm bruto = <strong>{item.closing_depletion_mm} mm</strong> primanjkljaja</li>)}</ul>:<p>Za to gredico še ni shranjene večdnevne bilance.</p>}
    </details>}
    <details><summary>Shranjeni izračuni za {day.day} ({saved.length})</summary><p>To so posnetki izračuna s takratnimi profili, ne dokazi izvedenega zalivanja. Sprememba profila jih ne preračuna.</p><ul>{saved.map(r=><li key={r.bed_id}>{r.crop} · gredica {r.bed}: {statusNames[r.status]} · {r.litres==null?"količina ni določena":`${r.litres} l`} · {r.day}</li>)}</ul></details>
    <h3>OpenSprinkler prek Home Assistanta</h3>
    <p>Pripravi osnutke iz shranjenih današnjih izračunov, največ šest ur starih. Pred tem shrani povezavo postaje in ponovno izračunaj dan. To ni samodejni zagon ventilov.</p>
    <button type="button" className="secondary-button" disabled={dirty||busy||osBusy} onClick={prepareOpenSprinkler}>PRIPRAVI AKCIJE OPENSPRINKLER</button>
    {osPreview&&<div aria-label="Osnutki OpenSprinkler"><p>{osPreview.note}</p>{!osPreview.rows.length&&<p>Za izbrani dan ni shranjenih izračunov.</p>}
      {osPreview.rows.map(r=><article key={r.bed_id}><strong>Gredica {r.bed||r.bed_id} · {r.status==="draft"?"Osnutek za ročni pregled":"Akcija ni pripravljena"}</strong>
        {r.status==="draft"?<><p>{r.litres} l · {r.run_seconds} sekund · {r.action.target.entity_id}</p><ul>{r.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul><p>Spodnji zapis lahko po preverjanju uporabiš v Home Assistantu, Orodja za razvijalce → Akcije → YAML. Izvedba tam dejansko odpre ventil.</p><textarea aria-label={`Akcija OpenSprinkler za gredico ${r.bed||r.bed_id}`} readOnly rows={8} value={r.yaml}/></>:<ul>{r.reasons.map((w,i)=><li key={i}>{w}</li>)}</ul>}
      </article>)}</div>}
    <h3>Smart Irrigation prek Home Assistanta</h3>
    <p>Stanje povezave: <strong>{haStatus?.connected?"povezano":haStatus?.configured?"nastavljeno, še nepreverjeno":"strežniška povezava ni nastavljena"}</strong>. URL Home Assistanta in žeton nastavi v okolju backend strežnika GrowMaster. Pri naslovu `.local` mora Docker vsebnik razrešiti mDNS; če ne, uporabi lokalni IP Home Assistanta.</p>
    <button type="button" className="secondary-button" disabled={haBusy||!haStatus?.configured} onClick={testHomeAssistant}>PREVERI POVEZAVO</button>
    <button type="button" className="secondary-button" disabled={haBusy||!haStatus?.configured} onClick={readHomeAssistantStates}>PREBERI NASTAVLJENE SENZORJE</button>
    {haStates&&<article aria-label="Stanja Home Assistant senzorjev"><h4>Prebrane vrednosti senzorjev</h4><p>{haStates.note} WH51: {haStates.configured_wh51_count}/{haStates.maximum_wh51_count} skupin.</p><ul>{haStates.sensor_groups.map(group=><li key={`${group.group_number}-${group.entity_id}`}><strong>{group.name}</strong>{group.group_number?` (${group.group_number})`:""} · {group.entity_id} · {group.assigned_beds} gredic {group.needs_migration?" · premakni v novo skupino":""}</li>)}</ul><ul>{haStates.entities.map(item=><li key={item.entity_id}><strong>{item.entity_id}</strong>: {item.available?`${item.state}${item.unit?` ${item.unit}`:""}`:item.issue||item.error||"nedosegljiv"}{item.last_updated?` · posodobljeno ${new Date(item.last_updated).toLocaleString()}`:""}</li>)}</ul>{Object.entries(haStates.numeric_summary_by_unit||{}).map(([unit,summary])=><p key={unit}>Povzetek {unit}: {summary.count} senzorjev · povprečje {summary.mean} · min {summary.minimum} · max {summary.maximum}</p>)}</article>}
    <p>Iz današnjih shranjenih izračunov pripravi Kc za trenutno aktivno kulturo in izbrano fazo. Po pregledu lahko GrowMaster Kc pošlje v Smart Irrigation. Ne zažene izračuna ali zalivanja; Smart Irrigation naj še naprej vodi svojo vremensko bilanco in urnik.</p>
    <button type="button" className="secondary-button" disabled={dirty||busy||siBusy} onClick={prepareSmartIrrigation}>PRIPRAVI Kc ZA SMART IRRIGATION</button>
    {siPreview&&<div aria-label="Osnutki Smart Irrigation"><p>{siPreview.note}</p>{!siPreview.rows.length&&<p>Za izbrani dan ni shranjenih dnevnih izračunov.</p>}
      {siPreview.rows.map(r=><article key={r.bed_id}><strong>Gredica {r.bed||r.bed_id} · {r.status==="draft"?"Osnutek za pregled":"Posodobitev ni pripravljena"}</strong>
        {r.status==="draft"?<><p>Kc {r.multiplier} · {r.action.target.entity_id}</p><textarea aria-label={`Smart Irrigation Kc za gredico ${r.bed||r.bed_id}`} readOnly rows={6} value={r.yaml}/></>:<ul>{r.reasons.map((w,i)=><li key={i}>{w}</li>)}</ul>}
      </article>)}</div>}
    {siPreview?.rows?.some(r=>r.status==="draft")&&<button type="button" className="primary-button" disabled={!haStatus?.configured||haBusy||dirty} onClick={sendSmartIrrigation}>POŠLJI Kc V HOME ASSISTANT</button>}
    <small>ETc = ET₀ × Kc. Voda v koreninah je ocenjena iz poljske kapacitete, točke venenja in globine korenin. Izračun ne modelira kapilarnega dotoka, odtoka ali rasti korenin. GrowMaster pošlje samo posodobitve Kc; ventilov ne odpira.</small>
  </section>;
}
