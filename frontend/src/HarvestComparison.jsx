import React, { useEffect, useState } from "react";
import { apiRequest } from "./platform";

const show = value => value ?? "—";
const offset = value => value == null ? "—" : `${value > 0 ? "+" : ""}${value} dni`;

export function HarvestComparison() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setReport(null); setError("");
    apiRequest("/api/planning/harvest-comparison").then(data => {
      if (!cancelled) setReport(data);
    }).catch(e => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [refresh]);
  return <section className="panel" aria-label="Napovedana in dejanska žetev">
    <div className="section-heading"><div><p className="eyebrow">Zgodovina žetve</p><h2>Napovedana in dejanska žetev</h2></div>
      <button type="button" className="secondary-button" onClick={() => setRefresh(n => n + 1)}>OSVEŽI PRIMERJAVO</button></div>
    <p>Primerjamo začetno napoved s prvim zabeleženim pobiranjem. Pozitiven odmik pomeni poznejšo žetev. Datumi in DTM ostanejo nespremenjeni; samodejno učenje še ni vključeno.</p>
    {error && <p role="alert">{error}</p>}
    {!report && !error && <p>Nalaganje primerjave …</p>}
    {report && <>
      <p>Primernih primerjav: {report.summary.eligible} / {report.summary.total} · V napovedanem intervalu: {report.summary.within_window} · Povprečna absolutna napaka: {report.summary.mean_absolute_error_days == null ? "—" : `${report.summary.mean_absolute_error_days} dni`}</p>
      <small>Prvo zabeleženo pobiranje je približek zrelosti. Na datum vplivajo tudi odločitve pri delu in manjkajoči zapisi.</small>
      {!report.rows.length && <p>Ni zasaditev za primerjavo.</p>}
      {report.rows.map(row => <details key={row.planting_id}>
        <summary>Gredica {row.bed} · {row.crop} · {row.variety} · setev {row.sowing_date}</summary>
        <p>Prvotno načrtovana žetev: {show(row.planned_harvest_date)} · Začetna napoved: {show(row.predicted_harvest_date)}</p>
        <p>Napovedani interval: {show(row.predicted_harvest_start)} – {show(row.predicted_harvest_end)}</p>
        <p>Prvo pobiranje: {show(row.first_harvest_date)} · Število pobiranj: {row.harvest_count} · Zaključek kulture: {show(row.completed_on)}</p>
        {row.eligible ? <>
          <p>Do prvega pobiranja: {row.days_from_initial_reference} dni od prvotnega datuma {row.reference_kind === "transplant" ? "presajanja" : "setve"} {row.reference_date}</p>
          <p>Odmik od prvotnega načrta: {offset(row.planned_error_days)} · Odmik od napovedi: {offset(row.prediction_error_days)} · V intervalu: {row.within_window ? "da" : "ne"}</p>
        </> : <p>{row.reason}</p>}
      </details>)}
    </>}
  </section>;
}
