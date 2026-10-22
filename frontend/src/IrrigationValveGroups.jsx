import React, {useEffect, useState} from "react";
import {apiRequest} from "./platform";

/** Plant all beds wired to the same valve in a single backend transaction. */
export function IrrigationValveGroups({crops,beds=[]}) {
  const [zones,setZones]=useState([]),[zoneId,setZoneId]=useState("");
  const [cropId,setCropId]=useState(""),[varietyId,setVarietyId]=useState("");
  const [sowingDate,setSowingDate]=useState("");
  const [suggestions,setSuggestions]=useState([]),[suggestBusy,setSuggestBusy]=useState(false),[suggestLoaded,setSuggestLoaded]=useState(false);
  const [overrideRotation,setOverrideRotation]=useState(false);
  const [confirmFinish,setConfirmFinish]=useState(false);
  const [cycleCount,setCycleCount]=useState(1),[cycleInterval,setCycleInterval]=useState(21);
  const [expectedYield,setExpectedYield]=useState("1");
  const [newName,setNewName]=useState(""),[controllerId,setControllerId]=useState("opensprinkler-1");
  const [stationNumber,setStationNumber]=useState("0"),[selectedBeds,setSelectedBeds]=useState([]);
  const [configBusy,setConfigBusy]=useState(false);
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState("");
  const refresh=async()=>{
    const data=await apiRequest("/api/irrigation/valves");
    setZones(data);
  };
  useEffect(()=>{refresh().catch(e=>setError(e.message));},[]);
  const zone=zones.find(z=>String(z.id)===zoneId);
  const crop=(crops||[]).find(c=>String(c.id)===cropId);
  const varieties=crop?.varieties||[];
  const register=async(e)=>{
    e.preventDefault();setError("");setMessage("");setConfigBusy(true);
    try{
      await apiRequest("/api/irrigation/valves",{
        method:"POST",body:JSON.stringify({
          name:newName,controller_id:controllerId,station_number:Number(stationNumber),
          bed_ids:selectedBeds
        })
      });
      await refresh();setSelectedBeds([]);setNewName("");
      setMessage("Fizični ventil in trajne gredice so registrirani. Ventil ostaja izklopljen.");
    }catch(e){setError(e.message);}finally{setConfigBusy(false);}
  };
  const assigned=new Set(zones.flatMap(z=>z.beds.map(b=>b.id)));
  const loadSuggestions=async()=>{
    if(!zoneId||!sowingDate)return;
    setSuggestBusy(true);setError("");
    try{
      const data=await apiRequest(`/api/irrigation/valves/${zoneId}/suggestions?sowing_date=${encodeURIComponent(sowingDate)}`);
      setSuggestions(data.suggestions||[]);setSuggestLoaded(true);
    }catch(e){setError(e.message);setSuggestions([]);setSuggestLoaded(false);}
    finally{setSuggestBusy(false);}
  };
  useEffect(()=>{setSuggestions([]);setSuggestLoaded(false);},[zoneId,sowingDate]);
  const planGroup=async()=>{
    if(!zone?.beds?.length||!cropId||!varietyId||!sowingDate)return;
    setBusy(true);setError("");setMessage("");
    try{
      const result=await apiRequest(`/api/irrigation/valves/${zoneId}/plans`,{
        method:"POST",body:JSON.stringify({
          bed_id:zone.beds[0].id,crop_id:Number(cropId),variety_id:Number(varietyId),
          sowing_date:sowingDate,expected_yield_kg:Number(expectedYield),
          succession_count:Number(cycleCount),succession_interval_days:Number(cycleInterval)
        })
      });
      setMessage(`Načrtovanih ${result.cycles} ciklov za ${result.bed_ids.length} gredic. Aktivacija ni izvedena.`);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  };
  const finishGroup=async()=>{
    if(!zoneId||!confirmFinish)return;
    setBusy(true);setError("");setMessage("");
    try{
      const result=await apiRequest(`/api/irrigation/valves/${zoneId}/finish`,{method:"POST"});
      setMessage(`Zaključenih je ${result.finished_planting_ids.length} zasaditev. Osvežite pregled zasaditev.`);
      setConfirmFinish(false);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  };
  const submit=async(e)=>{
    e.preventDefault();
    if(!zone?.beds?.length||!cropId||!varietyId||!sowingDate)return;
    setBusy(true);setError("");setMessage("");
    try {
      const result=await apiRequest(`/api/irrigation/valves/${zoneId}/plant`,{
        method:"POST",body:JSON.stringify({
          bed_id:zone.beds[0].id,crop_id:Number(cropId),
          variety_id:Number(varietyId),sowing_date:sowingDate,
          override_rotation:overrideRotation
        })
      });
      setMessage(`Zasaditev shranjena za ${result.plantings.length} gredic. Osvežite pregled zasaditev.`);
    }catch(e){setError(e.message);}
    finally{setBusy(false);}
  };
  return <section className="panel">
    <h3>Skupinska zasaditev po namakalnem ventilu</h3>
    <p>Vse gredice istega ventila dobijo isto kulturo, sorto in datum setve. Pred shranjevanjem se preveri kolobar vsake gredice.</p>
    <details>
      <summary>Trajna konfiguracija fizičnih ventilov</summary>
      <p>Priporočilo: en ventil za vsako gredico. Dva neodvisna krmilnika omogočata do 144 izhodov skupaj.</p>
      <form onSubmit={register}>
        <label>Ime ventila <input value={newName} onChange={e=>setNewName(e.target.value)} required maxLength={100}/></label>
        <label>Krmilnik <select value={controllerId} onChange={e=>setControllerId(e.target.value)}><option value="opensprinkler-1">OpenSprinkler 1</option><option value="opensprinkler-2">OpenSprinkler 2</option></select></label>
        <label>Številka izhoda (0–71) <input type="number" min="0" max="71" value={stationNumber} onChange={e=>setStationNumber(e.target.value)} required/></label>
        <fieldset><legend>Gredice na ventilu (priporočena ena)</legend>
          {beds.filter(b=>!assigned.has(b.id)).map(b=><label key={b.id}>
            <input type="checkbox" checked={selectedBeds.includes(b.id)}
              onChange={e=>setSelectedBeds(ids=>e.target.checked?[...ids,b.id]:ids.filter(id=>id!==b.id))}/>
            {b.name}
          </label>)}
        </fieldset>
        <button type="submit" disabled={configBusy||!selectedBeds.length}>{configBusy?"Shranjujem…":"Registriraj ventil in gredice"}</button>
      </form>
    </details>
    <form onSubmit={submit}>
      <label>Trajna namakalna skupina
        <select value={zoneId} onChange={e=>setZoneId(e.target.value)} required>
          <option value="">Izberite ventil</option>
          {zones.map(z=><option key={z.id} value={z.id}>{z.name} ({z.controller_id}, ventil {z.station_number})</option>)}
        </select>
      </label>
      {zone&&<p>Gredice: {zone.beds.map(b=>b.name).join(", ")||"Ni dodeljenih gredic"}</p>}
      <div>
        <button type="button" disabled={!zoneId||!sowingDate||suggestBusy} onClick={loadSuggestions}>
          {suggestBusy?"Preverjam kolobar…":"Predlagaj sorte za celotno skupino"}
        </button>
        {suggestLoaded&&suggestions.length===0&&<p>Za ta datum ni predlogov, ki bi ustrezali vsem gredicam.</p>}
        {suggestions.length>0&&<label>Predlogi brez kolobarskih opozoril
          <select defaultValue="" onChange={e=>{
            const [c,v]=e.target.value.split(":");
            setCropId(c||"");setVarietyId(v||"");
          }}>
            <option value="">Izberite predlog</option>
            {suggestions.map(x=><option key={x.variety_id} value={`${x.crop_id}:${x.variety_id}`}>
              {x.crop_name} – {x.variety_name} (ocena {x.score}, {x.maturity_days} dni)
            </option>)}
          </select>
        </label>}
      </div>
      <label>Kultura
        <select value={cropId} onChange={e=>{setCropId(e.target.value);setVarietyId("");}} required>
          <option value="">Izberite kulturo</option>
          {(crops||[]).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>
      <label>Sorta
        <select value={varietyId} onChange={e=>setVarietyId(e.target.value)} required>
          <option value="">Izberite sorto</option>
          {varieties.map(v=><option key={v.id} value={v.id}>{v.name}</option>)}
        </select>
      </label>
      <label>Datum setve <input type="date" value={sowingDate} onChange={e=>setSowingDate(e.target.value)} required/></label>
      <label><input type="checkbox" checked={overrideRotation} onChange={e=>setOverrideRotation(e.target.checked)}/> Izrecno potrjujem morebitno opozorilo glede kolobarja</label>
      <button type="submit" disabled={busy||!zone?.beds?.length||!varietyId||!sowingDate}>
        {busy?"Shranjujem…":"Zasadi vse gredice skupine"}
      </button>
    </form>
    {zone?.beds?.length>0&&<details>
      <summary>Načrtuj zaporedne setve za celotno skupino</summary>
      <p>Uporabljeni bodo zgoraj izbrana kultura, sorta in datum. Načrti se ne aktivirajo samodejno.</p>
      <label>Število ciklov <input type="number" min="1" max="20" value={cycleCount} onChange={e=>setCycleCount(e.target.value)}/></label>
      <label>Razmik med setvami (dni) <input type="number" min="1" max="365" value={cycleInterval} onChange={e=>setCycleInterval(e.target.value)}/></label>
      <label>Predviden pridelek na gredico (kg) <input type="number" min="0.01" step="0.1" value={expectedYield} onChange={e=>setExpectedYield(e.target.value)}/></label>
      <button type="button" disabled={busy||!cropId||!varietyId||!sowingDate||!(Number(expectedYield)>0)} onClick={planGroup}>
        Shrani načrte za vse gredice
      </button>
    </details>}
    {zone?.beds?.length>0&&<details>
      <summary>Zaključi celotno namakalno skupino</summary>
      <p>Zaključek velja za vse gredice tega ventila. Posamično zaključevanje ni dovoljeno.</p>
      <label><input type="checkbox" checked={confirmFinish} onChange={e=>setConfirmFinish(e.target.checked)}/>
        Potrjujem zaključek vseh aktivnih zasaditev izbrane skupine
      </label>
      <button type="button" disabled={!confirmFinish||busy} onClick={finishGroup}>
        Zaključi vse zasaditve skupine
      </button>
    </details>}
    {error&&<p role="alert">{error}</p>
    {message&&<p role="status">{message}</p>}
    {!zones.length&&<p>Ni nastavljenih fizičnih ventilov. Najprej je treba trajno povezati gredice in ventile.</p>}
  </section>;
}
