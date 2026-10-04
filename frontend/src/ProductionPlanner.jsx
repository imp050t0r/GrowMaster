import React, {useEffect,useRef,useState} from "react";
import {apiRequest} from "./platform";

export function ProductionPlanner({crops,plans,start,end,setStart,setEnd,onChoose}) {
  const [selected,setSelected]=useState([]),[maxBeds,setMaxBeds]=useState("5");
  const [report,setReport]=useState(null),[error,setError]=useState(""),[busy,setBusy]=useState(false),[notice,setNotice]=useState("");
  const request=useRef(0);
  useEffect(()=>{request.current++;setReport(null);setError("");setNotice("");setBusy(false);},[plans,crops,start,end,selected,maxBeds]);
  async function generate(event) {
    event.preventDefault();const current=++request.current;setBusy(true);setError("");setReport(null);setNotice("");
    try {
      const data=await apiRequest("/api/planning/production-proposals",{method:"POST",body:JSON.stringify({start,end,crop_ids:selected.map(Number),max_beds:Number(maxBeds)})});
      if(current===request.current)setReport(data);
    } catch(e) {if(current===request.current)setError(e.message);}
    finally {if(current===request.current)setBusy(false);}
  }
  return <section className="panel" aria-label="Predlog pridelave">
    <div className="section-heading"><div><p className="eyebrow">AI Production Planner · začetna različica</p><h2>Predlog pridelave</h2></div></div>
    <p>Izberi kulture in prihodnje obdobje za nove setve ter celotna okna prvih žetev. Obdobje je skupno s koledarjem in napovedmi spodaj.</p>
    <form className="planning-form" onSubmit={generate}>
      <label>Od<input type="date" required value={start} onChange={e=>setStart(e.target.value)} /></label>
      <label>Do<input type="date" required value={end} onChange={e=>setEnd(e.target.value)} /></label>
      <label>Kulture (največ 10)<select multiple value={selected} size="5" required onChange={e=>setSelected(Array.from(e.target.selectedOptions,option=>option.value))}>{crops.map(c=><option key={c.id} value={String(c.id)}>{c.name}</option>)}</select></label>
      <label>Največ novih gredic<input type="number" min="1" max="100" step="1" required value={maxBeds} onChange={e=>setMaxBeds(e.target.value)} /></label>
      <button className="primary-button" disabled={busy || !selected.length}>{busy?"PRIPRAVLJAM …":"PRIPRAVI PREDLOG"}</button>
    </form>
    <p>Lokalna pravila preverijo kolobar, sezono, način vzgoje in prosta obdobja gred. Zunanji AI model ni uporabljen. Količine pridelka, dovolj semena in razpoložljive ure niso zagotovljene.</p>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {report&&<><p>Predlogi: {report.proposals.length} · Obdobje: {report.start} – {report.end}</p>
      {!report.proposals.length&&<p>Ni ustreznega predloga. Preveri izbrane kulture, proste gredice in dolžino obdobja.</p>}
      {report.proposals.map(p=><article key={p.bed_id}>
        <strong>Gredica {p.bed} · {p.crop} · {p.variety}</strong>
        <p>Setev {p.sowing_date}{p.transplant_date?` · presajanje ${p.transplant_date}`:""} · prva žetev {p.predicted_harvest_start} – {p.predicted_harvest_end} · DTM {p.dynamic_dtm_days} dni</p>
        <ul>{p.reasons.map((reason,index)=><li key={index}>{reason}</li>)}</ul>
        {p.warnings.map((warning,index)=><p key={index}>{warning}</p>)}
        <button type="button" className="secondary-button" onClick={()=>{onChoose(p);setNotice(`Predlog za gredico ${p.bed} je prenesen v obrazec. Vnesi pričakovane kg, preveri podatke in izberi DODAJ V NAČRT. Predlog še ni shranjen.`);}}>PRENESI V OBRAZEC</button>
      </article>)}
      {report.unassigned_crops.length>0&&<p>Brez predloga: {report.unassigned_crops.map(c=>c.crop).join(", ")}. Povečaj število gred ali preveri omejitve.</p>}
      {report.skipped_beds.length>0&&<details><summary>Izpuščene gredice ({report.skipped_beds.length})</summary><ul>{report.skipped_beds.map(b=><li key={b.bed_id}>{b.bed}: {b.reason}</li>)}</ul></details>}
      <small>{report.note}</small>
    </>}
  </section>;
}
