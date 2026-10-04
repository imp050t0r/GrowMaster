import React, { useEffect, useState } from "react";
import { apiRequest } from "./platform";

export function DtmLearning({ plans, onApplied }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setReport(null);
    apiRequest("/api/planning/dtm-learning").then(data => {
      if (!cancelled) setReport(data);
    }).catch(e => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [plans, refresh]);

  async function change(planId, action) {
    if (!report || busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest(`/api/planning/dtm-learning/${planId}/${action}`, {
        method: "POST", body: JSON.stringify({ token: report.token }),
      });
      setNotice(result.message);
      await onApplied();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); setRefresh(n => n + 1); }
  }

  return <section className="panel" aria-label="Predlog popravka DTM iz zgodovine">
    <div className="section-heading"><div><p className="eyebrow">Učenje iz zgodovine</p><h2>Predlog popravka DTM</h2></div>
      <button type="button" className="secondary-button" disabled={busy} onClick={() => { setError(""); setRefresh(n => n + 1); }}>OSVEŽI PREDLOGE</button></div>
    <p>Predlog temelji na prvih zabeleženih pobiranjih iste sorte, sezone in načina štetja dni. Potrditev spremeni samo napoved izbranega prihodnjega načrta. Kataloški DTM in načrtovani datumi ostanejo ohranjeni.</p>
    <p>Preveri, ali so razmere in način pobiranja primerljivi. Podatki ne ločujejo vseh načinov pridelave; zanesljivost ostane nizka.</p>
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert">{error}</p>}
    {!report && !error && <p>Nalaganje predlogov …</p>}
    {report && !report.rows.length && <p>Ni odprtih načrtov.</p>}
    {report?.rows.map(row => <details key={row.plan_id} open={row.can_apply || row.applied}>
      <summary>Gredica {row.bed} · {row.crop} · {row.variety} · setev {row.sowing_date}</summary>
      <p>{row.reason}</p>
      <p>Primerljivih zapisov: {row.evidence.length} · Različnih začetnih datumov: {row.distinct_dates}</p>
      {(row.can_apply || row.applied) && <p>Napoved DTM: {row.before_days} → {row.after_days} dni · Popravek: {row.correction_days > 0 ? "+" : ""}{row.correction_days} dni · Predvidena prva žetev: {row.after_date}</p>}
      {row.evidence.length > 0 && <details><summary>Uporabljeni zapisi</summary><ul>{row.evidence.map(item => <li key={item.planting_id}>Zasaditev {item.planting_id} · začetek {item.reference_date} · prvo pobiranje {item.first_harvest_date} · odmik {item.error_days > 0 ? "+" : ""}{item.error_days} dni</li>)}</ul></details>}
      {row.can_apply && <button type="button" className="secondary-button" disabled={busy} onClick={() => change(row.plan_id, "apply")}>POTRDI POPRAVEK ZA TA NAČRT</button>}
      {row.can_reset && <button type="button" className="secondary-button" disabled={busy} onClick={() => change(row.plan_id, "reset")}>ODSTRANI POPRAVEK</button>}
    </details>)}
    <small>Premik sukcesije ali nov izračun napovedi zahteva ponovno presojo zgodovinskega popravka.</small>
  </section>;
}
