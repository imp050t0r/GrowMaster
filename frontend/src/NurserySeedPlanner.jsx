import React, {useEffect,useRef,useState} from "react";
import {apiRequest} from "./platform";

export function NurserySeedPlanner({plans,start,end}) {
  const [planId,setPlanId]=useState(""),[target,setTarget]=useState(""),[germination,setGermination]=useState("");
  const [survival,setSurvival]=useState(""),[reserve,setReserve]=useState("5");
  const [report,setReport]=useState(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const request=useRef(0);
  const eligible=(plans || []).filter(p=>p.status==="planned" && p.transplant_date && p.sowing_date>=start && p.sowing_date<=end);
  useEffect(()=>{
    request.current++;setReport(null);setError("");setBusy(false);
    return ()=>{request.current++;};
  },[plans,start,end,planId,target,germination,survival,reserve]);
  async function calculate(event) {
    event.preventDefault();const current=++request.current;setReport(null);setError("");setBusy(true);
    if(!eligible.some(p=>String(p.id)===planId)){setError("Izberi načrt v trenutnem obdobju.");setBusy(false);return;}
    try {
      const query=new URLSearchParams({target_plants:target,germination_pct:germination,nursery_survival_pct:survival,reserve_pct:reserve});
      const data=await apiRequest(`/api/seed-inventory/nursery-forecast/${planId}?${query}`);
      if(request.current===current)setReport(data);
    } catch(e) {if(request.current===current)setError(e.message);}
    finally {if(request.current===current)setBusy(false);}
  }
  const unitLabel=unit=>({g:"g",seeds:"semen",pellets:"peletov"}[unit] || unit);
  return <section aria-label="Seme za sadike">
    <h3>Seme za sadike</h3>
    <p>Izračun za izbrani načrt presajanja v obdobju koledarja. Vnesi želeno število uporabnih sadik, preverjeno kalivost semena in pričakovani delež uporabnih sadik po vzgoji. Izračun predpostavlja eno seme na sadiko.</p>
    {!eligible.length?<p>V obdobju ni načrtovanih setev za presajanje. Dodaj načrt z datumom setve in presajanja.</p>:<form className="planning-form" onSubmit={calculate}>
      <label>Načrt za sadike<select required value={eligible.some(p=>String(p.id)===planId)?planId:""} onChange={e=>{setPlanId(e.target.value);setTarget("");setGermination("");setSurvival("");}}><option value="">Izberi načrt</option>{eligible.map(p=><option key={p.id} value={String(p.id)}>{p.sowing_date} · {p.bed} · {p.crop} · {p.variety}</option>)}</select></label>
      <label>Potrebne uporabne sadike<input type="number" min="1" max="1000000" step="1" required value={target} onChange={e=>setTarget(e.target.value)}/></label>
      <label>Kalivost semena (%)<input type="number" min="0.01" max="100" step="0.01" required value={germination} onChange={e=>setGermination(e.target.value)}/></label>
      <label>Uporabne sadike po vzgoji (%)<input type="number" min="0.01" max="100" step="0.01" required value={survival} onChange={e=>setSurvival(e.target.value)}/></label>
      <label>Dodatna rezerva (%)<input type="number" min="0" max="100" step="0.1" required value={reserve} onChange={e=>setReserve(e.target.value)}/></label>
      <button className="primary-button" disabled={busy}>{busy?"RAČUNAM …":"IZRAČUNAJ SEME ZA SADIKE"}</button>
    </form>}
    {error&&<p role="alert">{error}</p>}
    {report&&<>
      <p><strong>{report.crop} · {report.variety} · gredica {report.bed}</strong></p>
      <p>Setev {report.sowing_date} · presajanje {report.transplant_date} · cilj {report.target_plants} uporabnih sadik</p>
      <p>Kalivost {report.germination_pct} % · uporabne sadike {report.nursery_survival_pct} % · rezerva {report.reserve_pct} %</p>
      <p>Potrebno: <strong>{report.required_quantity} semen</strong> · uporabna zaloga: {report.available_quantity} semen · primanjkljaj: {report.shortage} semen</p>
      {report.expired_quantity>0&&<p>{report.expired_quantity} semen ima rok pred setvijo in ni vključeno v uporabno zalogo.</p>}
      {report.stock_warnings.map((w,i)=><p key={i}>{w.message}</p>)}
      {report.shortage>0&&<>
        <h4>Možna pakiranja iz evidence</h4>
        {!report.packages.length&&<p>Za predlog pakiranj manjka veljavna velikost pakiranja ali masa tisoč semen za pretvorbo gramov.</p>}
        <ul>{report.packages.map((p,i)=><li key={i}>{p.packages_to_order} pakiranj po {p.package_size} {unitLabel(p.unit)} · skupaj {p.order_quantity} {unitLabel(p.unit)} · približno {p.seeds_per_package} semen na pakiranje{p.supplier?` · ${p.supplier}`:""}</li>)}</ul>
      </>}
      <small>{report.note}</small>
    </>}
    <p>Izračuni za več načrtov uporabljajo isto zalogo; ne seštevaj njihove pokritosti. Vrednosti veljajo za ta pogled in se ne shranijo v načrt.</p>
  </section>;
}
