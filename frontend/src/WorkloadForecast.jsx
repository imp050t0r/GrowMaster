import React, {useEffect,useState} from "react";
import {apiRequest} from "./platform";

export function WorkloadForecast({plans,start,end}) {
  const [report,setReport]=useState(null);
  const [error,setError]=useState("");
  const [capacity,setCapacity]=useState("");
  const [refresh,setRefresh]=useState(0);
  useEffect(()=>{
    let cancelled=false; setReport(null); setError("");
    if(!start || !end) return;
    apiRequest(`/api/planning/workload?start=${start}&end=${end}`).then(data=>{
      if(!cancelled) setReport(data);
    }).catch(e=>{if(!cancelled) setError(e.message);});
    return ()=>{cancelled=true;};
  },[plans,start,end,refresh]);
  return <section className="panel" aria-label="Tedenska napoved dela">
    <div className="section-heading"><div><p className="eyebrow">Workload Forecast</p><h2>Tedenska napoved dela</h2></div>
      <button type="button" className="secondary-button" onClick={()=>setRefresh(n=>n+1)}>OSVEŽI DELO</button></div>
    <p>Uporablja obdobje koledarja dela zgoraj. Sešteje načrtovane setve, presajanja, prve žetve, opravila in potrjene dostave. En zapis pomeni aktivnost, ne enake količine dela.</p>
    <label>Razpoložljive ure na teden za primerjavo<input type="number" min="0" step="0.5" value={capacity} onChange={e=>setCapacity(e.target.value)} /></label>
    <small>Ure so ocenjene le za opravila z vsaj tremi različnimi dnevi zaključenega dela iste vrste in enakih mer grede. Aktivnosti brez ocene niso vključene v ure. Vnesena razpoložljivost velja za ta pogled.</small>
    {error && <p role="alert">{error}</p>}
    {!report && !error && <p>Nalaganje napovedi …</p>}
    {report && <>
      <p>Aktivnosti: {report.activity_count} · Največ v enem tednu: {report.peak_week_activity_count}</p>
      {!report.activity_count && <p>V izbranem obdobju ni načrtovanega dela. Za pripravo na pomlad dodaj prihodnje načrte in izberi spomladansko obdobje.</p>}
      {report.weeks.filter(w=>w.activity_count).map(week=><details key={week.start}>
        <summary>{week.start} – {week.end} · {week.activity_count} aktivnosti</summary>
        <p>Setve: {week.counts.sowing} · Presajanja: {week.counts.transplant} · Prve žetve: {week.counts.planned_harvest} · Opravila: {week.counts.task} · Dostave: {week.counts.delivery}</p>
        <p>Delna ocena časa: {week.estimated_hours == null ? "ni dovolj zgodovine" : `${week.estimated_hours} ur`} · Aktivnosti brez ocene: {week.unknown_activity_count}</p>
        {capacity !== "" && week.estimated_hours != null && week.estimated_hours > Number(capacity) && <p>Ocenjeni del dela že presega vneseno tedensko razpoložljivost.</p>}
        {capacity !== "" && week.unknown_activity_count > 0 && <p>Zaradi manjkajočih ocen ni mogoče potrditi, da bo časa dovolj za vse delo.</p>}
        <ul>{week.activities.map((item,index)=><li key={`${item.type}-${index}`}>{item.date} · {item.title}{item.bed ? ` · gredica ${item.bed}` : ""} · {item.estimated_minutes == null ? "čas še ni ocenjen" : `${item.estimated_minutes} min (iz ${item.history_samples} zapisov)`}</li>)}</ul>
      </details>)}
    </>}
    <small>Žetev je termin prve načrtovane žetve; ponovljena pobiranja in še neustvarjena opravila niso vključena. Napoved ne spreminja koledarja.</small>
  </section>;
}
