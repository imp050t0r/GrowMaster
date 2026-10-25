import React, {useEffect, useRef, useState} from "react";
import {apiRequest} from "./platform";
import {sequencePreviewRuns} from "./irrigationHelpers";

const actions={valve_open:"Odpri ventil",valve_close:"Zapri ventil",pump_on:"Vklopi črpalko",pump_off:"Izklopi črpalko"};

export function IrrigationSequencePreview({zones}) {
  const [rows,setRows]=useState([]),[bedId,setBedId]=useState("");
  const [result,setResult]=useState(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const requestId=useRef(0);
  useEffect(()=>{
    requestId.current+=1;
    setRows([]);setBedId("");setResult(null);setError("");setBusy(false);
    return ()=>{requestId.current+=1;};
  },[zones]);
  const eligible=zones.filter(zone=>zone.beds?.length===1);
  const available=eligible.filter(zone=>!rows.some(row=>row.bed_id===zone.beds[0].id));
  const changeRows=next=>{setRows(next);setResult(null);setError("");};
  const move=(index,offset)=>{
    const next=[...rows];
    [next[index],next[index+offset]]=[next[index+offset],next[index]];
    changeRows(next);
  };
  const submit=async event=>{
    event.preventDefault();setResult(null);setError("");
    const id=++requestId.current;
    try{
      const runs=sequencePreviewRuns(rows,zones);
      setBusy(true);
      const preview=await apiRequest("/api/irrigation/sequence-preview",{method:"POST",body:JSON.stringify({runs})});
      if(id===requestId.current)setResult(preview);
    }catch(e){if(id===requestId.current)setError(e.message);}
    finally{if(id===requestId.current)setBusy(false);}
  };
  return <details className="irrigation-sequence-preview">
    <summary>Predogled zaporedja namakanja – simulacija</summary>
    <p>Predogled ne zažene ventilov ali črpalke. Trajanja vnesete ročno; ne pomenijo priporočenega odmerka vode.</p>
    {!eligible.length?<p>Najprej povežite vsaj eno gredico s samostojnim ventilom v trajni konfiguraciji.</p>:<form onSubmit={submit}>
      <fieldset disabled={busy}>
        <legend>Vrstni red gredic</legend>
        <label>Dodaj gredico <select value={bedId} onChange={e=>setBedId(e.target.value)}>
          <option value="">Izberite gredico</option>
          {available.map(zone=><option key={zone.id} value={zone.beds[0].id}>{zone.beds[0].name} – {zone.name}</option>)}
        </select></label>
        <button type="button" disabled={!bedId||rows.length>=144} onClick={()=>{
          changeRows([...rows,{bed_id:Number(bedId),run_seconds:"60"}]);setBedId("");
        }}>Dodaj v zaporedje</button>
        <ol>
          {rows.map((row,index)=>{
            const zone=eligible.find(zone=>zone.beds[0].id===row.bed_id);
            const name=zone?.beds[0].name||String(row.bed_id);
            return <li key={row.bed_id}>
              <strong>{name}</strong>
              <label>Trajanje za {name} (sekunde) <input type="number" min="1" max="86400" step="1" required value={row.run_seconds}
                onChange={e=>changeRows(rows.map((item,i)=>i===index?{...item,run_seconds:e.target.value}:item))}/></label>
              <button type="button" disabled={index===0} aria-label={`Premakni ${name} prej`} onClick={()=>move(index,-1)}>Prej</button>
              <button type="button" disabled={index===rows.length-1} aria-label={`Premakni ${name} pozneje`} onClick={()=>move(index,1)}>Pozneje</button>
              <button type="button" aria-label={`Odstrani ${name}`} onClick={()=>changeRows(rows.filter((_,i)=>i!==index))}>Odstrani</button>
            </li>;
          })}
        </ol>
        <p>Podana trajanja ne vključujejo 5-sekundnih zamikov in prekrivanja ventilov. Simulirate lahko tudi izključene ventile.</p>
        <button type="submit" disabled={!rows.length}>{busy?"Pripravljam predogled…":"Prikaži časovnico"}</button>
      </fieldset>
    </form>}
    {error&&<p role="alert">{error}</p>}
    {result&&<div role="status">
      <p><strong>Samo simulacija. Skupni čas: {result.total_seconds} s.</strong> Čas vključuje zamike in prekrivanje.</p>
      <ol>
        {result.events.map((event,index)=>{
          const run=result.runs.find(run=>run.controller_id===event.controller_id&&run.station_number===event.station_number);
          const zone=eligible.find(zone=>zone.beds[0].id===run?.bed_id);
          return <li key={index}><strong>{event.at_seconds} s:</strong> {actions[event.action]}
            {run&&<> – {zone?.beds[0].name||`Gredica ${run.bed_id}`} ({run.controller_id}, izhod {run.station_number}; {run.valve_enabled?"omogočen":"izključen"})</>}
          </li>;
        })}
      </ol>
      <p>Predpostavljeno začetno stanje: črpalka je izključena, ventili so zaprti. Dejanska stanja in hidravlične omejitve niso preverjeni.</p>
    </div>}
  </details>;
}
