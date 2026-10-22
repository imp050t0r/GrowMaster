import React, {useEffect, useState} from "react";
import {apiRequest} from "./platform";

/** Plant all beds wired to the same valve in a single backend transaction. */
export function IrrigationValveGroups({crops}) {
  const [zones,setZones]=useState([]),[zoneId,setZoneId]=useState("");
  const [cropId,setCropId]=useState(""),[varietyId,setVarietyId]=useState("");
  const [sowingDate,setSowingDate]=useState("");
  const [overrideRotation,setOverrideRotation]=useState(false);
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState("");
  const refresh=async()=>{
    const data=await apiRequest("/api/irrigation/valves");
    setZones(data);
  };
  useEffect(()=>{refresh().catch(e=>setError(e.message));},[]);
  const zone=zones.find(z=>String(z.id)===zoneId);
  const crop=(crops||[]).find(c=>String(c.id)===cropId);
  const varieties=crop?.varieties||[];
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
    <form onSubmit={submit}>
      <label>Trajna namakalna skupina
        <select value={zoneId} onChange={e=>setZoneId(e.target.value)} required>
          <option value="">Izberite ventil</option>
          {zones.map(z=><option key={z.id} value={z.id}>{z.name} ({z.controller_id}, ventil {z.station_number})</option>)}
        </select>
      </label>
      {zone&&<p>Gredice: {zone.beds.map(b=>b.name).join(", ")||"Ni dodeljenih gredic"}</p>}
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
    {error&&<p role="alert">{error}</p>}
    {message&&<p role="status">{message}</p>}
    {!zones.length&&<p>Ni nastavljenih fizičnih ventilov. Najprej je treba trajno povezati gredice in ventile.</p>}
  </section>;
}
