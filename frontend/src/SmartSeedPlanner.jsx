import React, {useEffect,useState} from "react";
import {apiRequest} from "./platform";
import {NurserySeedPlanner} from "./NurserySeedPlanner";
export function SmartSeedPlanner({plans,start,end}) {
  const [report,setReport]=useState(null),[error,setError]=useState(""),[refresh,setRefresh]=useState(0);
  useEffect(()=>{
    let cancelled=false; setReport(null); setError("");
    const days=(Date.parse(end)-Date.parse(start))/86400000;
    if(!Number.isFinite(days)||days<1||days>365){setError("Izberi obdobje od 1 do 365 dni.");return;}
    apiRequest(`/api/seed-inventory/forecast?start_date=${start}&horizon_days=${days}`).then(data=>{if(!cancelled)setReport(data);}).catch(e=>{if(!cancelled)setError(e.message);});
    return ()=>{cancelled=true;};
  },[plans,start,end,refresh]);
  return <section className="panel" aria-label="Načrtovalnik semena">
    <div className="section-heading"><div><p className="eyebrow">Smart Seed Planner</p><h2>Načrtovalnik semena</h2></div><button type="button" className="secondary-button" onClick={()=>setRefresh(n=>n+1)}>OSVEŽI SEME</button></div>
    <p>Potrebe neposrednih setev v obdobju koledarja, z 5 % rezerve. Zalogo razporedi po rokih uporabnosti in datumih setve. Napoved ne rezervira in ne odšteva zaloge; druge rezervacije niso vključene.</p>
    {error&&<p role="alert">{error}</p>}{!report&&!error&&<p>Nalaganje potreb …</p>}
    {report&&<><p>Načrtovane setve: {report.planned_sowings} · Sorte s primanjkljajem: {report.summary.order}</p>
      {!report.planned_sowings&&<p>Dodaj prihodnje načrte setev in izberi ustrezno obdobje.</p>}
      {report.items.map(item=><details key={`${item.crop}-${item.variety}`}><summary>{item.crop} · {item.variety} · {item.shortage>0?`Manjka ${item.shortage} g`:"Zaloga zadostuje"}</summary>
        <p>Potreba: {item.required_quantity} g · Uporabna zaloga za načrt: {item.available_quantity} g</p>
        {item.shortage>0&&<p>Potrebno do: {item.first_shortage_date} · {item.packages_to_order==null?"Vnesi velikost pakiranja za predlog nakupa.":`${item.packages_to_order} pakiranj po ${item.package_size} g (${item.order_quantity} g)`}</p>}
        {item.expired_quantity>0&&<p>{item.expired_quantity} g neporabljene zaloge ima rok pred zadnjo setvijo.</p>}
        <ul>{item.plans.map(p=><li key={p.crop_plan_id}>{p.sowing_date} · {p.bed} · {p.required_quantity} g · primanjkljaj {p.shortage} g</li>)}</ul>
        {item.stock_warnings.map((w,i)=><p key={i}>{w.message}</p>)}
      </details>)}
      {report.warnings.map(w=><p key={w.crop_plan_id}>{w.sowing_date} · {w.crop} · {w.variety}: {w.message}</p>)}
    </>}
    <small>Zaloga brez roka je vključena z opozorilom. Upoštevane so samo serije iste sorte; obloženo seme se ne pretvarja v grame. Potrebe sadik izračunaj posebej spodaj.</small>
    <NurserySeedPlanner plans={plans} start={start} end={end}/>
  </section>;
}
