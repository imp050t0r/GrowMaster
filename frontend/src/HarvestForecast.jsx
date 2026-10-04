import React, {useEffect,useState} from "react";
import {apiRequest} from "./platform";

export function HarvestForecast({plans,start,end}) {
  const [report,setReport]=useState(null),[error,setError]=useState(""),[refresh,setRefresh]=useState(0);
  useEffect(()=>{
    let cancelled=false; setReport(null); setError("");
    if(!start || !end) return;
    apiRequest(`/api/planning/harvest-forecast?start=${start}&end=${end}`).then(data=>{
      if(!cancelled) setReport(data);
    }).catch(e=>{if(!cancelled) setError(e.message);});
    return ()=>{cancelled=true;};
  },[plans,start,end,refresh]);
  const quantity = value => value == null ? "količina ni določena" : `${value} kg (vnesena ocena)`;
  return <section className="panel" aria-label="Tedenska napoved žetve">
    <div className="section-heading"><div><p className="eyebrow">Harvest Forecast</p><h2>Tedenska napoved žetve</h2></div>
      <button type="button" className="secondary-button" onClick={()=>setRefresh(n=>n+1)}>OSVEŽI ŽETEV</button></div>
    <p>Uporablja obdobje koledarja zgoraj. Prve žetve so razporejene po sredinskem datumu shranjenega okna Dynamic DTM. Brez veljavnega okna je uporabljen načrtovani datum.</p>
    {error && <p role="alert">{error}</p>}{!report && !error && <p>Nalaganje napovedi …</p>}
    {report && <>
      <p>Okna prvih žetev v obdobju: {report.first_harvest_count} · Brez veljavnega DTM: {report.fallback_count} · Dejansko pobrano v obdobju: {report.actual_kg} kg</p>
      {report.overdue_count>0 && <p role="status">Pri {report.overdue_count} zasaditvah ali načrtih je okno že poteklo. Preveri datume in evidenco pobiranja; napoved jih ne premika samodejno.</p>}
      {!report.first_harvest_count && <p>V obdobju ni okna prihodnje prve žetve. Dodaj načrte ali izberi spomladansko obdobje.</p>}
      {report.weeks.filter(w=>w.scheduled_count || w.window_overlap_count || w.actual_kg).map(week=><details key={week.start}>
        <summary>{week.start} – {week.end} · Prve žetve po sredinskem datumu: {week.scheduled_count}</summary>
        <p>Delna načrtovana količina: {quantity(week.scheduled_kg)} · Brez tedenske količine: {week.unknown_quantity_count} · Dejansko pobrano: {week.actual_kg} kg</p>
        <p>Okna, ki segajo v ta teden: {week.window_overlap_count}. Isto okno lahko sega v več tednov; teh števil ne seštevaj.</p>
        <ul>{week.rows.map(row=><li key={`${row.source}-${row.id}`}>{row.crop} · {row.variety} · gredica {row.bed} · {row.source==="planting" ? "aktivna zasaditev" : "načrt"} · {quantity(row.scheduled_first_harvest_kg)}</li>)}</ul>
      </details>)}
      {report.rows.length>0 && <details><summary>Okna in pojasnila za posamezne gredice</summary>
        {report.rows.map(row=><article key={`${row.source}-${row.id}`}>
          <strong>{row.crop} · {row.variety} · gredica {row.bed}</strong>
          <p>{row.window_start} – {row.window_end} · sredinski datum {row.center_date} · {row.basis==="dynamic" ? `Dynamic DTM, kakovost podatkov: ${{low:"nizka",medium:"srednja",unknown:"ni določena"}[row.confidence] || "ni določena"}` : "načrtovani datum"}</p>
          <p>Načrtovani datum: {row.planned_harvest_date} · Vneseni pridelek za cel cikel: {quantity(row.planned_cycle_kg)}</p>
          {row.warning && <p>{row.warning}</p>}{row.quantity_reason && <p>{row.quantity_reason}</p>}
        </article>)}
      </details>}
    </>}
    <small>Kilogrami so vnesene ocene, ne napoved biološkega pridelka. Pri sortah, ki podpirajo večkratno pobiranje, količine niso razdeljene po tednih. Zasaditve z že zabeleženo prvo žetvijo niso vključene v prihodnje prve žetve; prihodnja pobiranja niso ocenjena. Dejanska žetev vključuje vsa pobiranja v obdobju brez odpada, zato neposredna primerjava z delno napovedjo ni ocena točnosti. Pregled ne spreminja datumov ali zaloge.</small>
  </section>;
}
