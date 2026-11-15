import React, {useEffect, useRef, useState} from "react";
import {apiRequest} from "./platform";
import "./fertilization.css";

const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;};
const emptyDose=()=>({day:today(),planting_id:"",material:"",quantity_kg:"",area_m2:"",n_pct:"",p2o5_pct:"",k2o_pct:"",composition_source:"",notes:"",rationale:""});
const emptySoil=()=>({sampled_on:today(),source:"",sample_area:"",method:"",nutrient_unit:"",ph:"",organic_matter_pct:"",phosphorus:"",potassium:"",notes:""});
const names={draft:"Osnutek",confirmed:"Potrjeno",applied:"Izvedeno",cancelled:"Preklicano"};
const numberOrNull=v=>v===""?null:Number(v);

export function FertilizationPlanner({beds}) {
  const [bedId,setBedId]=useState(""),[data,setData]=useState(null),[error,setError]=useState(""),[message,setMessage]=useState("");
  const [busy,setBusy]=useState(false),[dose,setDose]=useState(emptyDose),[soil,setSoil]=useState(emptySoil),[mode,setMode]=useState("plan");
  const [reviewer,setReviewer]=useState(""),[appliedOn,setAppliedOn]=useState(today),[voidReason,setVoidReason]=useState("");
  const generation=useRef(0);
  async function load(id=bedId) {
    const n=++generation.current;
    if(!id){setData(null);return;}
    const result=await apiRequest(`/api/fertilization/beds/${id}`);
    if(n===generation.current)setData(result);
  }
  useEffect(()=>{setData(null);setError("");setMessage("");setDose({...emptyDose(),area_m2:beds.find(b=>String(b.id)===bedId)?.area_m2||""});setSoil(emptySoil());
    load(bedId).catch(e=>setError(e.message));return()=>{generation.current++;};
  },[bedId]);
  async function write(path,payload,after) {
    setBusy(true);setError("");setMessage("");
    try {await apiRequest(`/api/fertilization/${path}`,{method:"POST",body:JSON.stringify(payload)});await load();after?.();setMessage("Shranjeno.");}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  function field(value,setter,key,label,{type="text",required=true,min,max}={}) {
    return <label>{label}<input type={type} required={required} min={min} max={max} step={type==="number"?"any":undefined} value={value[key]} onChange={e=>setter({...value,[key]:e.target.value})}/></label>;
  }
  function saveDose(e) {
    e.preventDefault();
    const {rationale,...values}=dose;
    const payload={...values,planting_id:dose.planting_id?Number(dose.planting_id):null,area_m2:Number(dose.area_m2),quantity_kg:Number(dose.quantity_kg),n_pct:numberOrNull(dose.n_pct),p2o5_pct:numberOrNull(dose.p2o5_pct),k2o_pct:numberOrNull(dose.k2o_pct)};
    if(mode==="plan")Object.assign(payload,{rationale,context_version:data.context_version});
    write(`beds/${bedId}/${mode==="plan"?"plans":"applications"}`,payload,()=>setDose({...emptyDose(),area_m2:data.area_m2}));
  }
  function saveSoil(e) {
    e.preventDefault();const payload={...soil};
    for(const key of ["ph","organic_matter_pct","phosphorus","potassium"])payload[key]=numberOrNull(soil[key]);
    write(`beds/${bedId}/soil-tests`,payload,()=>setSoil(emptySoil()));
  }
  return <section className="panel fertilization-panel">
    <div className="section-heading"><div><p className="eyebrow">Gredica in posevek</p><h2>Gnojenje</h2></div></div>
    <p>Ročno načrtovanje in evidenca. Potrditev načrta ne pomeni izvedenega gnojenja in ne vključi doziranja.</p>
    <label>Gredica<select value={bedId} disabled={busy} onChange={e=>setBedId(e.target.value)}><option value="">Izberi gredico</option>{beds.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    {data&&<fieldset disabled={busy}>
      {data.warnings.map(w=><p key={w}>{w}</p>)}
      <h3>Zgodovina posevkov</h3>
      {data.plantings.length?<ul>{data.plantings.map(p=><li key={p.id}>{p.crop} · {p.variety} · {p.sowing_date} – {p.completed_on||"v teku"} · {p.status==="active"?"aktiven":"zaključen"} · evidentiran pridelek {data.harvests.filter(h=>h.planting_id===p.id).reduce((sum,h)=>sum+h.quantity_kg,0).toFixed(2)} kg</li>)}</ul>:<p>Ni evidentiranih posevkov.</p>}
      <h3>Analize tal</h3>
      {data.soil_tests.length?<ul>{data.soil_tests.map(s=><li key={s.id}>{s.sampled_on} · {s.source} · {s.sample_area} · {s.method}: pH {s.ph??"—"}, organska snov {s.organic_matter_pct??"—"} %, P {s.phosphorus??"—"}, K {s.potassium??"—"} ({s.nutrient_unit}). {s.notes}</li>)}</ul>:<p>Analiza še ni vnesena. Brez nje ni mogoče zanesljivo določiti odmerka.</p>}
      <details><summary>Dodaj analizo tal</summary><form onSubmit={saveSoil} className="fertilization-form">
        {field(soil,setSoil,"sampled_on","Datum vzorčenja",{type:"date",max:today()})}
        {field(soil,setSoil,"source","Laboratorij / oznaka izvida")}{field(soil,setSoil,"sample_area","Območje vzorčenja")}{field(soil,setSoil,"method","Metoda analize (z izvida)")}{field(soil,setSoil,"nutrient_unit","Enota in oblika P/K (z izvida)")}
        {[["ph","pH",14],["organic_matter_pct","Organska snov (%)",100],["phosphorus","Fosfor"],["potassium","Kalij"]].map(([key,label,max])=><React.Fragment key={key}>{field(soil,setSoil,key,label,{type:"number",required:false,min:0,max})}</React.Fragment>)}
        {field(soil,setSoil,"notes","Opombe",{required:false})}<button className="primary-button">Shrani analizo</button>
      </form></details>
      <h3>Deklarirana hranila iz izvedenih vnosov</h3>
      <ul>{[["n","N"],["p2o5","P₂O₅"],["k2o","K₂O"]].map(([key,label])=><li key={key}>{label}: {data.declared_totals[key].known_kg} kg znanih vnosov; {data.declared_totals[key].unknown_applications} vnosov z neznano sestavo.</li>)}</ul>
      <details><summary>Dodaj obrok ali izvedeno gnojenje</summary>
        <label>Vrsta vnosa<select value={mode} onChange={e=>setMode(e.target.value)}><option value="plan">Načrtovani obrok</option><option value="actual">Že izvedeno gnojenje</option></select></label>
        <form onSubmit={saveDose} className="fertilization-form">
          <label>Posevek<select required={mode==="plan"} value={dose.planting_id} onChange={e=>setDose({...dose,planting_id:e.target.value})}><option value="">Brez povezave s posevkom</option>{data.plantings.filter(p=>mode!=="plan"||p.status==="active").map(p=><option key={p.id} value={p.id}>{p.crop} · {p.sowing_date}</option>)}</select></label>
          {field(dose,setDose,"day",mode==="plan"?"Načrtovani datum":"Datum izvedbe",{type:"date",min:mode==="plan"?today():undefined,max:mode!=="plan"?today():undefined})}
          {field(dose,setDose,"material","Gnojilo / kompost")}{field(dose,setDose,"quantity_kg","Količina pripravka (kg)",{type:"number",min:0.000001})}{field(dose,setDose,"area_m2","Obravnavana površina (m²)",{type:"number",min:0.000001,max:data.area_m2})}
          {[["n_pct","N (%)"],["p2o5_pct","P₂O₅ (%)"],["k2o_pct","K₂O (%)"]].map(([key,label])=><React.Fragment key={key}>{field(dose,setDose,key,label,{type:"number",required:false,min:0,max:100})}</React.Fragment>)}
          {field(dose,setDose,"composition_source","Vir sestave (deklaracija / analiza)",{required:[dose.n_pct,dose.p2o5_pct,dose.k2o_pct].some(v=>v!=="")})}
          {field(dose,setDose,"notes","Ostanki posevka in druge opombe",{required:false})}
          {mode==="plan"&&field(dose,setDose,"rationale","Utemeljitev odmerka: kultura, analiza, pretekli vnosi")}
          <p>Prazna sestava pomeni neznano. Vnesi maso pripravka; litrov brez pretvorbe z znano gostoto ne vpisuj kot kilograme.</p>
          <button className="primary-button">{mode==="plan"?"Shrani osnutek":"Zabeleži izvedeno gnojenje"}</button>
        </form>
      </details>
      <h3>Načrtovani obroki</h3>
      <label>Pregledal/a (za potrditev)<input value={reviewer} onChange={e=>setReviewer(e.target.value)} maxLength={120}/></label>
      <label>Datum dejanske izvedbe<input type="date" value={appliedOn} max={today()} onChange={e=>setAppliedOn(e.target.value)}/></label>
      {data.plans.length?data.plans.map(p=><article className="fertilization-record" key={p.id}>
        <strong>{p.day} · {p.material} · {p.quantity_kg} kg / {p.area_m2} m² · {names[p.status]}</strong>
        <p>{data.plantings.find(x=>x.id===p.planting_id)?.crop} · {p.rationale}</p><p>N {p.n_pct??"?"} %, P₂O₅ {p.p2o5_pct??"?"} %, K₂O {p.k2o_pct??"?"} % · {p.composition_source} · {p.notes}</p>
        {p.reviewer&&<p>Potrdil/a: {p.reviewer}</p>}
        {["draft","confirmed"].includes(p.status)&&<>{p.stale&&<p>Podatki so se spremenili. Prekliči načrt in pripravi novega.</p>}
          {p.status==="draft"&&<button disabled={p.stale||!reviewer.trim()} onClick={()=>write(`plans/${p.id}/confirm`,{reviewer,context_version:data.context_version})}>Potrdi pregledani načrt</button>}
          {p.status==="confirmed"&&<button disabled={p.stale||!appliedOn} onClick={()=>write(`plans/${p.id}/complete`,{applied_on:appliedOn})}>Zabeleži izvedbo te količine</button>}
          <button onClick={()=>write(`plans/${p.id}/cancel`,{})}>Prekliči načrt</button></>}
      </article>):<p>Ni načrtovanih obrokov.</p>}
      <h3>Izvedeno gnojenje</h3>
      <label>Razlog popravka napačnega vnosa<input value={voidReason} onChange={e=>setVoidReason(e.target.value)} maxLength={1000}/></label>
      {data.applications.length?<ul>{data.applications.map(a=><li key={a.id}>{a.day} · {a.material} · {a.quantity_kg} kg / {a.area_m2} m² · N {a.n_pct??"?"} %, P₂O₅ {a.p2o5_pct??"?"} %, K₂O {a.k2o_pct??"?"} % · {a.notes}
        {a.void_reason?<strong> · Razveljavljeno: {a.void_reason}</strong>:<button disabled={!voidReason.trim()} onClick={()=>write(`applications/${a.id}/void`,{reason:voidReason},()=>setVoidReason(""))}>Razveljavi napačen vnos</button>}</li>)}</ul>:<p>Ni evidentiranih vnosov.</p>}
    </fieldset>}
  </section>;
}
