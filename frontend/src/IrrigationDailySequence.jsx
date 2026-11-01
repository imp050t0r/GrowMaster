import React, {useEffect, useRef, useState} from "react";
import {apiRequest} from "./platform";

const actions={valve_open:"Odpri ventil",valve_close:"Zapri ventil",pump_on:"Vklopi črpalko",pump_off:"Izklopi črpalko"};
const statuses={draft:"Dnevni osnutek",blocked:"Načrt je blokiran",no_irrigation:"Brez predlaganega zalivanja"};
const rowStatuses={irrigate:"Potrebuje vodo",hold:"Brez zalivanja",blocked:"Potreben pregled"};

export function IrrigationDailySequence({day,beds,profiles,saved}) {
  const [result,setResult]=useState(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const requestId=useRef(0);
  useEffect(()=>{
    requestId.current++;setResult(null);setError("");setBusy(false);
    return()=>{requestId.current++;};
  },[day,beds,profiles,saved]);
  async function refresh() {
    const id=++requestId.current;
    setResult(null);setError("");setBusy(true);
    try {
      const preview=await apiRequest(`/api/irrigation/daily-sequence-preview?day=${encodeURIComponent(day)}`);
      if(preview.simulation_only!==true||preview.automatic_execution!==false||!statuses[preview.status])throw new Error("Odgovor ni veljaven dnevni predogled.");
      if(id===requestId.current)setResult(preview);
    } catch(e) {if(id===requestId.current)setError(e.message);}
    finally {if(id===requestId.current)setBusy(false);}
  }
  return <details className="irrigation-sequence-preview">
    <summary>Dnevni načrt za OpenSprinkler – samo predogled</summary>
    <p>GrowMaster pripravi zaporedje iz shranjenih dnevnih bilanc in preverljivih vremenskih podatkov. Na voljo je samo za današnji dan v Sloveniji.</p>
    <button type="button" disabled={busy} onClick={refresh}>{busy?"Preverjam dnevne podatke…":"Pripravi dnevni predogled"}</button>
    {error&&<p role="alert">{error}</p>}
    {result&&<div role="status">
      <h4>{statuses[result.status]} · {result.day}</h4>
      <p><strong>Predogled ne pošlje ukazov OpenSprinklerju ali črpalki.</strong> Ni evidenca izvedbe in ne preprečuje ponovnega zalivanja.</p>
      <p>To je posnetek shranjenih podatkov. Po spremembi ventilov ali drugih podatkov ponovno pripravi predogled. Neshranjeni vnosi niso vključeni.</p>
      {result.reasons.map((reason,i)=><p key={i}>{reason}</p>)}
      {!result.rows.length&&<p>Ni aktivnih posevkov za dnevno zaporedje.</p>}
      <ul>{result.rows.map(row=>{
        const run=result.runs.find(r=>r.bed_id===row.bed_id);
        return <li key={row.bed_id}><strong>{row.bed}: {rowStatuses[row.status]||"Potreben pregled"}</strong>
          {row.requested_litres!=null&&<> · izračunana potreba {row.requested_litres} l</>}
          {row.estimated_litres!=null&&<> · ocenjena količina v zaporedju {row.estimated_litres} l</>}
          {row.pump_active_seconds!=null&&<> · čas ventila ob delujoči črpalki {row.pump_active_seconds} s (s prekrivanjem)</>}
          {run&&<> · {run.controller_id}, izhod {run.station_number} (številčenje od 0) · {run.valve_enabled?"ventil omogočen":"ventil izključen – dovoljena je le simulacija"}</>}
          {row.reasons.map((reason,i)=><p key={i}>{reason}</p>)}
        </li>;
      })}</ul>
      {result.status==="blocked"&&<p>Zaporedje ni pripravljeno za nobeno gredico. Najprej odpravi navedene razloge in ponovno shrani potrebne dnevne bilance.</p>}
      {result.status==="draft"&&<>
        <p>Skupni čas zaporedja: {result.total_seconds} s. Vključuje 5-sekundne zamike in prekrivanje ventilov.</p>
        <ol>{result.events.map((event,i)=>{
          const run=result.runs.find(r=>r.controller_id===event.controller_id&&r.station_number===event.station_number);
          const bed=result.rows.find(row=>row.bed_id===run?.bed_id);
          return <li key={i}>{event.at_seconds} s: {actions[event.action]}{run&&<> · {bed?.bed||`Gredica ${run.bed_id}`} · {run.controller_id}, izhod {run.station_number}</>}</li>;
        })}</ol>
      </>}
      <p>{result.note}</p>
    </div>}
  </details>;
}
