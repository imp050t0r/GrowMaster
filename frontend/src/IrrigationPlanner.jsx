import React, {useEffect, useRef, useState} from "react";
import {apiRequest} from "./platform";
import {cropIdForBed,dailyBedStates} from "./irrigationHelpers";

const cropEmpty={kc_initial:"",kc_mid:"",kc_late:"",root_depth_m:"",depletion_fraction:"",source:""};
const bedEmpty={mode:"smart_irrigation",valve_mode:"individual",irrigation_zone:"",wh51_group:null,field_capacity_pct:"",wilting_point_pct:"",efficiency_pct:"",flow_l_min:"",dripline_total_length_m:"",emitter_spacing_cm:"",emitter_flow_l_h:"",max_application_mm:"",sensor_dry_pct:"",sensor_wet_pct:"",source:"",opensprinkler_station_entity:null,smart_irrigation_entity:null,max_run_seconds:3600};
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
  const [siPreview,setSiPreview]=useState(null),[siBusy,setSiBusy]=useState(false),[siConfirmed,setSiConfirmed]=useState(false);
  const siGeneration=useRef(0);
  const [haStatus,setHaStatus]=useState(null),[haBusy,setHaBusy]=useState(false);
  const [haConfig,setHaConfig]=useState({url:"",token:""});
  const [autoConfig,setAutoConfig]=useState({enabled:false,run_after_local_time:"07:00",last_runs:[]});
  const [haStates,setHaStates]=useState(null);
  function chooseBed(value) {
    setBedId(value);
    const bed=beds.find(item=>String(item.id)===String(value));
    setCropId(cropIdForBed(bed,crops));
  }
  useEffect(()=>{let closed=false; apiRequest("/api/irrigation/profiles").then(p=>{if(!closed){setProfiles(p);setSensorGroups(Array.from({length:16},(_,i)=>p.sensor_groups?.find(item=>item.group_number===i+1)||{group_number:i+1,name:`WH51 ${i+1}`,entity_id:""}));}}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;generation.current++;};},[]);
  useEffect(()=>{let closed=false;apiRequest("/api/irrigation/home-assistant/status").then(r=>{if(!closed){setHaStatus(r);setHaConfig(value=>({...value,url:r.url||""}));}}).catch(()=>{if(!closed)setHaStatus({configured:false,token_configured:false});});return()=>{closed=true;};},[]);
  useEffect(()=>{let closed=false;apiRequest("/api/irrigation/automatic-irrigation").then(r=>{if(!closed)setAutoConfig(r);}).catch(()=>{});return()=>{closed=true;};},[]);
  useEffect(()=>{setCp(profiles.crops.find(p=>String(p.crop_id)===cropId)||cropEmpty);},[cropId,profiles]);
  useEffect(()=>{setBp({...bedEmpty,...profiles.beds.find(p=>String(p.bed_id)===bedId)});},[bedId,profiles]);
  useEffect(()=>{generation.current++;setReport(null);setMessage("");setBusy(false);},[cropId,bedId,cp,bp,day]);
  useEffect(()=>{let closed=false;setSaved([]);apiRequest(`/api/irrigation/daily?day=${day.day}`).then(r=>{if(!closed)setSaved(r.rows);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[day.day]);
  useEffect(()=>{
    let closed=false;
    const refresh=()=>apiRequest(`/api/irrigation/daily-readiness?day=${day.day}`)
      .then(r=>{if(!closed)setReadiness(r);})
      .catch(e=>{if(!closed)setError(e.message);});
    setReadiness(null);
    refresh();
    const timer=window.setInterval(refresh,15*60*1000);
    const onVisibilityChange=()=>{if(document.visibilityState==="visible")refresh();};
    document.addEventListener("visibilitychange",onVisibilityChange);
    return()=>{closed=true;window.clearInterval(timer);document.removeEventListener("visibilitychange",onVisibilityChange);};
  },[day.day,saved,beds,profiles]);
  useEffect(()=>{let closed=false;setLedger([]);setLedgerOpening("");setLedgerRain("0");setLedgerApplied("0");if(!bedId)return()=>{closed=true;};apiRequest(`/api/irrigation/water-ledger?bed_id=${bedId}&through=${day.day}`).then(r=>{if(!closed){const rows=r.rows||[];setLedger(rows);const current=rows.find(item=>item.day===day.day);const previous=rows.at(-1);const opening=current?.opening_depletion_mm??previous?.closing_depletion_mm;if(opening!=null){setLedgerOpening(String(opening));setDay(value=>({...value,initial_depletion_mm:String(opening)}));}if(current){setLedgerRain(String(current.effective_rain_mm));setLedgerApplied(String(current.applied_irrigation_mm));}}}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[bedId,day.day]);
  useEffect(()=>{osGeneration.current++;setOsPreview(null);setOsBusy(false);siGeneration.current++;setSiPreview(null);setSiBusy(false);setSiConfirmed(false);return()=>{osGeneration.current++;siGeneration.current++;};},[profiles,saved,day,cp,bp,cropId,bedId]);
  function numeric(form) {return Object.fromEntries(Object.entries(form).filter(([k])=>!["crop_id","bed_id"].includes(k)).map(([k,v])=>[k,["mode","valve_mode","source","irrigation_zone"].includes(k)?v||null:["opensprinkler_station_entity","smart_irrigation_entity"].includes(k)?v||null:v===""||v==null?null:Number(v)]));}
  async function prepareOpenSprinkler() {
    const n=++osGeneration.current;setOsBusy(true);setOsPreview(null);setError("");
    try {const r=await apiRequest(`/api/irrigation/opensprinkler?day=${day.day}`);if(n===osGeneration.current)setOsPreview(r);}
    catch(e){if(n===osGeneration.current)setError(e.message);}finally{if(n===osGeneration.current)setOsBusy(false);}
  }
  async function prepareSmartIrrigation() {
    const n=++siGeneration.current;setSiBusy(true);setSiPreview(null);setSiConfirmed(false);setError("");
    try {const r=await apiRequest(`/api/irrigation/smart-irrigation?day=${day.day}`);if(n===siGeneration.current)setSiPreview(r);}
    catch(e){if(n===siGeneration.current)setError(e.message);}finally{if(n===siGeneration.current)setSiBusy(false);}
  }
  async function saveAutomaticIrrigationSettings(enabled=autoConfig.enabled) {
    setHaBusy(true);setError("");setMessage("");
    try {
      const r=await apiRequest("/api/irrigation/automatic-irrigation",{method:"PUT",body:JSON.stringify({...autoConfig,enabled})});
      setAutoConfig(value=>({...value,...r}));setMessage(r.message||"Nastavitve samodejnega zalivanja so shranjene.");
    } catch(e){setError(e.message);} finally {setHaBusy(false);}
  }
  async function setAutomaticIrrigation(enabled) {
    if(enabled&&!window.confirm("Vklopim samodejno zalivanje? GrowMaster bo po izbrani lokalni uri uporabil svež Smart Irrigation izračun in lahko odpre povezane OpenSprinkler ventile."))return;
    await saveAutomaticIrrigationSettings(enabled);
  }
  async function testHomeAssistant() {
    setHaBusy(true);setError("");setMessage("");
    try {const r=await apiRequest("/api/irrigation/home-assistant/test",{method:"POST"});setHaStatus(previous=>({...previous,configured:true,connected:true}));setMessage(`Povezava s Home Assistantom deluje (${r.message}).`);}
    catch(e){setError(e.message);}finally{setHaBusy(false);}
  }
  async function saveHomeAssistantConfig(event) {
    event.preventDefault();setHaBusy(true);setError("");setMessage("");
    try {
      const r=await apiRequest("/api/irrigation/home-assistant/config",{method:"PUT",body:JSON.stringify(haConfig)});
      setHaStatus({...r,connected:false});setHaConfig({url:r.url,token:""});
      setMessage("Povezava je varno shranjena. Zdaj izberi PREVERI POVEZAVO.");
    } catch(e){setError(e.message);} finally {setHaBusy(false);}
  }
  async function clearHomeAssistantConfig() {
    if(!window.confirm("Izbrišem povezavo Home Assistanta, shranjeno v GrowMasterju?"))return;
    setHaBusy(true);setError("");setMessage("");setHaStates(null);
    try {
      const r=await apiRequest("/api/irrigation/home-assistant/config",{method:"DELETE"});
      setHaStatus({...r,connected:false});setHaConfig({url:r.url||"",token:""});
      setMessage(r.configured?"Nastavitev iz aplikacije je izbrisana; še vedno je nastavljena povezava iz okolja strežnika.":"Povezava Home Assistanta je izbrisana.");
    } catch(e){setError(e.message);} finally {setHaBusy(false);}
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
  const driplineInputs=[bp.dripline_total_length_m,bp.emitter_spacing_cm,bp.emitter_flow_l_h].map(Number);
  const hasDriplineInputs=[bp.dripline_total_length_m,bp.emitter_spacing_cm,bp.emitter_flow_l_h].every(v=>v!==""&&v!=null&&Number(v)>0);
  const calculatedFlow=hasDriplineInputs?driplineInputs[0]/(driplineInputs[1]/100)*driplineInputs[2]/60:null;
  const reportByBed=new Map(saved.map(item=>[item.bed_id,item]));
  const dailyStates=dailyBedStates(beds,crops,profiles,saved);
  const dirty=JSON.stringify(numeric(cp))!==JSON.stringify(numeric(storedCrop||cropEmpty))||JSON.stringify(numeric(bp))!==JSON.stringify(numeric({...bedEmpty,...storedBed}));
  return <section className="panel" aria-label="Namakanje">
    <p className="eyebrow">Dnevna vodna bilanca</p><h2>Namakanje</h2>
    <p>Dnevni pregled uporablja trenutno aktivno kulturo. Za gredice brez WH51 GrowMaster prebere sveže trajanje Smart Irrigation in iz nastavljenega pretoka oceni količino vode. Pregled se osveži ob odprtju, ob vrnitvi v aplikacijo in vsakih 15 minut. Ročni vodni izračun ET₀, dežja in začetnega primanjkljaja je ločen. Ročni OpenSprinkler osnutek je namenjen pregledu in sam ne zažene ventila. Ločena avtomatika deluje samo, če jo izrecno vklopiš.</p>
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
      <p>{readiness.note}</p><ul>{readiness.rows.map(row=><li key={row.bed_id}><strong>{row.bed} · {row.crop}{row.variety?` (${row.variety})`:""}</strong>{row.suggested_stage?` · faza ${row.suggested_stage==="initial"?"začetna":row.suggested_stage==="mid"?"polna rast":"pozna"} (${row.stage_progress_pct}% cikla)`:" · faza ni določena"} · {row.mode==="smart_irrigation"?`Smart Irrigation: ${row.smart_irrigation_seconds==null?"ni izračuna":`${row.smart_irrigation_seconds} sekund`} · ${row.estimated_litres==null?"pretok ni vpisan":`≈ ${row.estimated_litres} l`} · ${row.kc_sync_status==="matched"?`Kc ${row.kc_expected} usklajen`:row.kc_sync_status==="needs_update"?`Kc ${row.smart_irrigation_multiplier} → ${row.kc_expected}, posodobi`:row.kc_sync_status==="unknown"?"Kc ni preverjen":"Kc ni uporabljen"} · ${row.decision==="irrigate"?"zalivanje priporočeno":row.decision==="hold"?"zalivanje ni potrebno":"pregled potreben"}`:`WH51 skupina ${row.wh51_group_name||row.wh51_group||"ni dodeljena"} · ${row.sensor_group_beds} gredic`} {!row.ready?` · ${row.reasons.join(" ")}`:" · pripravljeno"}{row.action&&<><p>Osnutek za ročni pregled: {row.action.target.entity_id} · {row.action.data.run_seconds} sekund</p><textarea aria-label={`Osnutek OpenSprinkler za gredico ${row.bed}`} readOnly rows={6} value={`action: opensprinkler.run_station\ntarget:\n  entity_id: ${row.action.target.entity_id}\ndata:\n  run_seconds: ${row.action.data.run_seconds}\n  queue_option: append`}/></>}</li>)}</ul>
      {readiness.valve_groups?.map(group=><article key={group.station} aria-label={`Skupni ventil ${group.station}`}><strong>Skupni ventil · gredice {group.bed_ids.join(", ")} · {group.status==="draft"?`${group.run_seconds} sekund · približno ${group.estimated_litres} l`:"blokirano"}</strong>{group.status==="draft"&&<p>Ocena vode po gredici: {group.bed_water_estimates.map(item=>`${readiness.rows.find(row=>row.bed_id===item.bed_id)?.bed||`gredica ${item.bed_id}`}: ${item.litres} l`).join(" · ")}. Dejanska količina je odvisna od izmerjenega pretoka posamezne veje.</p>}{group.reasons.map((reason,index)=><p key={index}>{reason}</p>)}{group.action&&<textarea aria-label={`Akcija za skupni ventil ${group.station}`} readOnly rows={6} value={`action: opensprinkler.run_station\ntarget:\n  entity_id: ${group.station}\ndata:\n  run_seconds: ${group.run_seconds}\n  queue_option: append`}/>}</article>)}
    </article>}
    <div className="range-form"><label>Kultura<select value={cropId} onChange={e=>setCropId(e.target.value)}><option value="">Izberi kulturo</option>{crops.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label>Gredica<select value={bedId} onChange={e=>chooseBed(e.target.value)}><option value="">Izberi gredico</option>{beds.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label></div>
    {currentPlanting&&<p className="irrigation-current-crop">Trenutna zasaditev GrowMasterja: <strong>{currentPlanting.crop} {currentPlanting.variety||""}</strong> · setev {currentPlanting.sowing_date}. Če je bila zasaditev v resnici že zamenjana, najprej posodobi evidenco setve.</p>}
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    {!!profiles.planning_conflicts?.length&&<section role="alert" aria-label="Konflikti načrtov na skupnih ventilih"><strong>Vodnim profilom ne ustrezajo vsi shranjeni načrti oziroma zasaditve.</strong><p>Izmerjeni podatki so ohranjeni. Pred nadaljevanjem preveri naslednje zapise:</p><ul>{profiles.planning_conflicts.map(item=><li key={`${item.record_type}-${item.record_id}`}>Gredica {item.bed} · {item.record_type==="plans"?"načrt":"zasaditev"} {item.record_id}: {item.reasons.join(" ")}</li>)}</ul></section>}
    <details><summary>Profil kulture — koeficienti in korenine</summary>
      <p>Vnesi preverjene koeficiente za svojo kulturo in način pridelave. Globina je trenutna učinkovita globina korenin, ne največja globina odrasle rastline. Delež izsušitve je med 0 in 1.</p>
      <form className="planning-form" onSubmit={e=>{e.preventDefault();saveProfile("crops");}}>
        {field(cp,setCp,"kc_initial","Kc — začetna faza",0,2)}{field(cp,setCp,"kc_mid","Kc — polna rast",0,2)}{field(cp,setCp,"kc_late","Kc — pozna faza",0,2)}
        {field(cp,setCp,"root_depth_m","Učinkovita globina korenin (m)",0.001,3)}{field(cp,setCp,"depletion_fraction","Dovoljeni delež izsušitve",0.001,0.999)}
        <label>Vir profila kulture<input required maxLength={500} value={cp.source} onChange={e=>setCp({...cp,source:e.target.value})}/></label>
        <button className="secondary-button" disabled={!cropId||busy}>SHRANI PROFIL KULTURE</button>
      </form></details>
    <details><summary>Profil grede — tla, pretok in WH51</summary>
      <p>Poljska kapaciteta in točka venenja sta volumenska deleža vode v tleh, ne odstotka WH51. Pretok pomeni skupni pretok vseh kapljičnih cevi na izbrani gredici.</p>
      <form className="planning-form" onSubmit={e=>{e.preventDefault();saveProfile("beds");}}>
        <label>Način namakanja<select value={bp.mode||"smart_irrigation"} onChange={e=>setBp({...bp,mode:e.target.value})}><option value="soil_sensor">S senzorjem vlage v tleh</option><option value="smart_irrigation">Brez talnega senzorja — Smart Irrigation</option></select></label>
        {bp.mode==="soil_sensor"?<p>Način z merjenjem: za pripravljeno dnevno bilanco zahteva svež, povezan senzor tal. Njegova meritev preverja vodno bilanco.</p>:<p>Način brez talnega senzorja: Smart Irrigation vodi vremensko bilanco. Dnevni pregled GrowMasterja prebere njegovo izračunano trajanje; za oceno litrov moraš nastaviti pretok grede.</p>}
        <label>Namakalna cona (1–16)<select value={bp.irrigation_zone||""} onChange={e=>setBp({...bp,irrigation_zone:e.target.value})}><option value="">Izberi cono</option>{Array.from({length:16},(_,i)=><option key={i+1} value={`zone_${i+1}`}>Cona {i+1}</option>)}</select></label>
        {field(bp,setBp,"field_capacity_pct","Poljska kapaciteta (% vol.)",0.001,70)}{field(bp,setBp,"wilting_point_pct","Točka venenja (% vol.)",0,69.999)}
        {field(bp,setBp,"efficiency_pct","Učinkovitost namakanja (%)",0.001,100)}
        <h4>Pretok kapljičnih cevi</h4>
        <p>Vnesi vsoto dolžin vseh kapljičnih cevi na tej gredici. GrowMaster izračuna število kapljačev in skupni pretok. Pretok kapljača vnesi pri dejanskem delovnem tlaku.</p>
        {field(bp,setBp,"dripline_total_length_m","Skupna dolžina vseh cevi na gredici (m)",0.001,100000,true)}
        {field(bp,setBp,"emitter_spacing_cm","Razmik med kapljači (cm)",0.001,500,true)}
        {field(bp,setBp,"emitter_flow_l_h","Pretok enega kapljača (l/h)",0.001,100,true)}
        {hasDriplineInputs?<p>Izračunani skupni pretok: <strong>{calculatedFlow.toFixed(2)} l/min</strong> (ocenjeno { (driplineInputs[0]/(driplineInputs[1]/100)).toFixed(1)} kapljačev). Ob skupnem ventilu se za čas zalivanja sešteje pretok vseh dodeljenih gredic.</p>:<>{[bp.dripline_total_length_m,bp.emitter_spacing_cm,bp.emitter_flow_l_h].some(v=>v!==""&&v!=null)&&<p>Za izračun pretoka izpolni vsa tri polja.</p>}{field(bp,setBp,"flow_l_min","Skupni pretok vseh kapljičnih cevi (l/min), če ga vneseš ročno",0.001,10000,true)}</>}
        {field(bp,setBp,"max_application_mm","Največji enkratni odmerek (mm)",0.001,100)}{field(bp,setBp,"sensor_dry_pct","Umerjeni suhi prag WH51 (%)",0,100,true)}{field(bp,setBp,"sensor_wet_pct","Umerjeni mokri prag WH51 (%)",0,100,true)}
        <label>Vir profila tal in umerjanja<input required maxLength={500} value={bp.source} onChange={e=>setBp({...bp,source:e.target.value})}/></label>
        <label>Razporeditev ventila<select value={bp.valve_mode||"individual"} onChange={e=>setBp({...bp,valve_mode:e.target.value})}><option value="individual">Individualni ventil — samo ta gredica</option><option value="shared">Skupni ventil — deli ga več gredic</option></select></label>
        <label>Postaja OpenSprinkler v Home Assistantu<input placeholder="switch.greda_1_station_enabled" pattern="switch\.[a-z0-9_]+" maxLength={150} value={bp.opensprinkler_station_entity||""} onChange={e=>setBp({...bp,opensprinkler_station_entity:e.target.value})}/></label>
        {bp.valve_mode==="shared"&&<p>Na vseh gredicah tega ventila izberi »Skupni ventil« in isti OpenSprinkler entity ID. V načinu Smart Irrigation vpiši tudi isto SI cono; v Home Assistantu nastavi njeno površino in pretok kot vsoto vseh teh gredic (m² in l/min). GrowMaster pripravi en Kc in en skupni čas. Vse gredice morajo imeti aktivno, namakalno združljivo zasaditev; najnižja omejitev odmerka in časa velja za celoten ventil.</p>}
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
    <p>Pripravi osnutke iz shranjenih današnjih izračunov, največ šest ur starih. Pred tem shrani povezavo postaje in ponovno izračunaj dan. Ta gumb pripravi le ročni osnutek; za samodejni zagon uporabi ločen izbirni nadzor spodaj.</p>
    <button type="button" className="secondary-button" disabled={dirty||busy||osBusy} onClick={prepareOpenSprinkler}>PRIPRAVI AKCIJE OPENSPRINKLER</button>
    {osPreview&&<div aria-label="Osnutki OpenSprinkler"><p>{osPreview.note}</p>{!osPreview.rows.length&&<p>Za izbrani dan ni shranjenih izračunov.</p>}
      {osPreview.rows.map(r=><article key={r.bed_id}><strong>Gredica {r.bed||r.bed_id} · {r.status==="draft"?"Osnutek za ročni pregled":"Akcija ni pripravljena"}</strong>
        {r.status==="draft"?<><p>{r.litres} l · {r.run_seconds} sekund · {r.action.target.entity_id}</p><ul>{r.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul><p>Spodnji zapis lahko po preverjanju uporabiš v Home Assistantu, Orodja za razvijalce → Akcije → YAML. Izvedba tam dejansko odpre ventil.</p><textarea aria-label={`Akcija OpenSprinkler za gredico ${r.bed||r.bed_id}`} readOnly rows={8} value={r.yaml}/></>:<ul>{r.reasons.map((w,i)=><li key={i}>{w}</li>)}</ul>}
      </article>)}</div>}
    <section className="irrigation-automation">
      <h3>Samodejno zalivanje</h3>
      <p>Ko je vključeno, GrowMaster po lokalni uri preverja sveže Smart Irrigation izračune. Pred odpiranjem ventila preveri aktivno kulturo, Kc, povezavo ventila, čas in omejitev zalivanja. Po vklopu in ob spremembi Kc počaka na nov Smart Irrigation izračun cone. Negotovega HA odgovora ne ponovi samodejno.</p>
      <label>Začni preverjanje po lokalni uri <input type="time" value={autoConfig.run_after_local_time||"07:00"} onChange={e=>setAutoConfig({...autoConfig,run_after_local_time:e.target.value})}/></label>
      <button type="button" className="secondary-button" disabled={haBusy||!haStatus?.configured} onClick={()=>saveAutomaticIrrigationSettings()}>SHRANI URNIK</button>
      <p>Stanje avtomatike: <strong>{autoConfig.enabled?"VKLOPLJENA":"IZKLOPLJENA"}</strong></p>
      <button type="button" className={autoConfig.enabled?"secondary-button":"primary-button"} disabled={haBusy||!haStatus?.configured} onClick={()=>setAutomaticIrrigation(!autoConfig.enabled)}>
        {autoConfig.enabled?"IZKLOPI SAMODEJNO ZALIVANJE":"VKLOPI SAMODEJNO ZALIVANJE"}
      </button>
      {autoConfig.last_runs?.length>0&&<details><summary>Zadnji samodejni zagoni</summary><ul>{autoConfig.last_runs.map((run,i)=><li key={i}>{run.day} · {run.station} · {run.status} · {run.run_seconds} s</li>)}</ul></details>}
    </section>
    <h3>Smart Irrigation prek Home Assistanta</h3>
    <p>Stanje povezave: <strong>{haStatus?.connected?"povezano":haStatus?.configured?"nastavljeno, še nepreverjeno":"ni nastavljena"}</strong>. Vnesi URL Home Assistanta, ki je dosegljiv iz računalnika GrowMaster, in njegov dolgoročni dostopni žeton. Žeton se shrani šifrirano na podatkovni disk strežnika in ga GrowMaster ne prikaže nazaj. Za naslov `.local` mora biti ime dosegljivo iz Docker vsebnika; sicer uporabi lokalni IP.</p>
    {haStatus?.source==="environment"&&haStatus?.configured&&<p>Trenutno je uporabljena starejša strežniška nastavitev. Če shraniš obrazec, bo nastavitev iz aplikacije prevzela prednost.</p>}
    <form className="planning-form" onSubmit={saveHomeAssistantConfig}>
      <label>URL Home Assistanta<input type="url" required maxLength={2048} placeholder="http://192.168.1.50:8123" value={haConfig.url} onChange={e=>setHaConfig({...haConfig,url:e.target.value})}/></label>
      <label>Dolgoročni dostopni žeton<input type="password" autoComplete="new-password" maxLength={8192} required={!haStatus?.token_configured} placeholder={haStatus?.token_configured?"Shranjeni žeton ostane, če polje pustiš prazno":"Prilepi žeton iz Home Assistanta"} value={haConfig.token} onChange={e=>setHaConfig({...haConfig,token:e.target.value})}/></label>
      <button className="secondary-button" disabled={haBusy}>SHRANI POVEZAVO</button>
    </form>
    {haStatus?.source==="application"&&<button type="button" className="danger-button" disabled={haBusy} onClick={clearHomeAssistantConfig}>IZBRIŠI POVEZAVO</button>}
    <button type="button" className="secondary-button" disabled={haBusy||!haStatus?.configured} onClick={testHomeAssistant}>PREVERI POVEZAVO</button>
    <button type="button" className="secondary-button" disabled={haBusy||!haStatus?.configured} onClick={readHomeAssistantStates}>PREBERI NASTAVLJENE SENZORJE</button>
    {haStates&&<article aria-label="Stanja Home Assistant senzorjev"><h4>Prebrane vrednosti senzorjev</h4><p>{haStates.note} WH51: {haStates.configured_wh51_count}/{haStates.maximum_wh51_count} skupin.</p><ul>{haStates.sensor_groups.map(group=><li key={`${group.group_number}-${group.entity_id}`}><strong>{group.name}</strong>{group.group_number?` (${group.group_number})`:""} · {group.entity_id} · {group.assigned_beds} gredic {group.needs_migration?" · premakni v novo skupino":""}</li>)}</ul><ul>{haStates.entities.map(item=><li key={item.entity_id}><strong>{item.entity_id}</strong>: {item.available?`${item.state}${item.unit?` ${item.unit}`:""}`:item.issue||item.error||"nedosegljiv"}{item.last_updated?` · posodobljeno ${new Date(item.last_updated).toLocaleString()}`:""}</li>)}</ul>{Object.entries(haStates.numeric_summary_by_unit||{}).map(([unit,summary])=><p key={unit}>Povzetek {unit}: {summary.count} senzorjev · povprečje {summary.mean} · min {summary.minimum} · max {summary.maximum}</p>)}</article>}
    <p>GrowMaster primerja Kc aktivne kulture in samodejno določene faze s trenutnim atributom multiplier v Smart Irrigation. Ob neskladju dnevni pregled označi gredico za pregled in ne pripravi osnutka ventila. Po pošiljanju Kc počakaj, da Smart Irrigation po svojem urniku ponovno izračuna cono.</p>
    <button type="button" className="secondary-button" disabled={dirty||busy||siBusy} onClick={prepareSmartIrrigation}>PRIPRAVI Kc ZA SMART IRRIGATION</button>
    {siPreview&&<div aria-label="Osnutki Smart Irrigation"><p>{siPreview.note}</p>{!siPreview.rows.length&&<p>Ni aktivnih gredic za pripravo Kc.</p>}
      {siPreview.rows.map(r=><article key={r.bed_id}><strong>Gredica {r.bed||r.bed_id} · {r.status==="draft"?"Osnutek za pregled":"Posodobitev ni pripravljena"}</strong>
        {r.status==="draft"?<><p>{r.crop} · faza: {r.stage==="initial"?"začetna":r.stage==="mid"?"polna rast":"pozna"} ({r.stage_progress_pct}% rastnega cikla) · Kc {r.multiplier} · {r.action.target.entity_id}</p><p>Fazo je GrowMaster določil iz datuma setve in pričakovanega pobiranja.</p><textarea aria-label={`Smart Irrigation Kc za gredico ${r.bed||r.bed_id}`} readOnly rows={6} value={r.yaml}/></>:<ul>{r.reasons.map((w,i)=><li key={i}>{w}</li>)}</ul>}
      </article>)}</div>}
    {siPreview?.rows?.some(r=>r.status==="draft")&&<><label><input type="checkbox" checked={siConfirmed} onChange={e=>setSiConfirmed(e.target.checked)}/> Potrjujem, da sem preveril aktivno kulturo, profil Kc in HA cono za vse prikazane gredice. Fazo je GrowMaster izračunal iz datumov zasaditve.</label><button type="button" className="primary-button" disabled={!siConfirmed||!haStatus?.configured||haBusy||dirty} onClick={sendSmartIrrigation}>POŠLJI Kc V HOME ASSISTANT</button></>}
    <small>ETc = ET₀ × Kc. Voda v koreninah je ocenjena iz poljske kapacitete, točke venenja in globine korenin. Izračun ne modelira kapilarnega dotoka, odtoka ali rasti korenin. GrowMaster pošlje samo posodobitve Kc; ventilov ne odpira.</small>
  </section>;
}
