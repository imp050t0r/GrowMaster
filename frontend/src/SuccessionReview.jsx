import React, { useEffect, useState } from "react";
import { apiRequest } from "./platform";
import "./succession.css";

function ReleaseDate({ item, recordType, recordId, busy, save }) {
  const [value, setValue] = useState(item.expected_bed_release_date || "");
  useEffect(() => setValue(item.expected_bed_release_date || ""), [item.expected_bed_release_date]);
  return <form className="succession-release" onSubmit={event => {
    event.preventDefault(); save(recordType, recordId, value || null);
  }}>
    <label>Zadnji dan zasedenosti grede<input type="date" value={value} min={item.minimum_release_date}
      onChange={event => setValue(event.target.value)} disabled={busy} /></label>
    <button className="secondary-button" disabled={busy}>SHRANI ZAKLJUČEK</button>
    <small>Prazen datum odstrani ročni zaključek. Pri večkratnem pobiranju datum prve žetve ni dovolj.{recordType === "plans" && " Datum velja za trenutni načrt; ob uporabi premika se premakne tudi ta datum."}</small>
  </form>;
}

export function SuccessionReview({ plans, onApplied }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setReport(null);
    apiRequest("/api/planning/successions").then(data => {
      if (!cancelled) setReport(data);
    }).catch(e => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [plans, refresh]);

  async function change(path, method, payload) {
    if (!report || busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest(path, { method, body: JSON.stringify({ token: report.token, ...payload }) });
      setNotice(result.message);
      await onApplied();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      setRefresh(value => value + 1);
    }
  }
  const save = (type, id, value) => change(`/api/planning/successions/${type}/${id}/release`, "PUT", { expected_bed_release_date: value });
  return <section className="panel succession-panel" aria-label="Dinamične sukcesije">
    <div className="section-heading"><div><p className="eyebrow">Dynamic Succession Engine</p><h2>Zaporedje kultur in konflikti</h2></div>
      <button type="button" className="secondary-button" disabled={busy} onClick={() => { setError(""); setRefresh(value => value + 1); }}>OSVEŽI</button></div>
    {error && <p role="alert" className="succession-warning">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!report && !error && <p>Preverjam zaporedje …</p>}
    {report && <><p>{report.note}</p>
      {!report.beds.length && <p className="empty-state">Ni aktivnih ali načrtovanih zasaditev.</p>}
      {report.beds.map(group => <details className="succession-bed" key={group.bed_id} open={group.change_count > 0 || group.plans.some(p => p.blocked)}>
        <summary>Gredica {group.bed} · {group.plans.length} načrtov{group.change_count > 0 ? ` · ${group.change_count} predlaganih premikov` : ""}{group.plans.some(p => p.blocked) ? " · potreben pregled" : ""}</summary>
        {group.active.map(item => <article key={`active-${item.id}`}>
          <strong>Trenutno raste: {item.label}</strong>
          <p>{item.occupied_through ? `Predvidoma zasedena do ${item.occupied_through}` : item.basis === "active_overdue" ? "Napovedani zaključek je minil, cikel pa je še aktiven. Preveri stanje na gredi." : "Zaključek zasedenosti še ni določen."}</p>
          <ReleaseDate item={item} recordType="plantings" recordId={item.id} busy={busy} save={save} />
        </article>)}
        {group.plans.map(row => <article key={row.plan_id}>
          <strong>{row.label}</strong>
          <p>{row.blocked ? "Sprostitve grede še ni mogoče oceniti." : row.shift_days ? `Časovni konflikt: predlagan premik za ${row.shift_days} dni.` : "V predhodnem zaporedju ni zaznanega časovnega konflikta."}</p>
          {row.predecessors.length > 0 && <small>Predhodna kultura: {row.predecessors.join("; ")}</small>}
          <div className="succession-dates">
            <span>Setev: {row.original.sowing_date}{row.shift_days > 0 && !row.blocked && <b> → {row.proposed.sowing_date}</b>}</span>
            {row.original.transplant_date && <span>Presajanje: {row.original.transplant_date}{row.shift_days > 0 && !row.blocked && <b> → {row.proposed.transplant_date}</b>} · vzgoja sadik {row.nursery_days} dni</span>}
            <span>Načrtovana žetev: {row.original.expected_harvest_date}{row.shift_days > 0 && !row.blocked && <b> → {row.proposed.expected_harvest_date}</b>}</span>
            <span>Predvidoma zasedena do: {row.occupied_through || "potreben datum zaključka"}</span>
          </div>
          {row.warnings.map((warning, i) => <p className="succession-warning" key={i}>{warning}</p>)}
          <ReleaseDate item={{ ...row.original, minimum_release_date: row.minimum_release_date }} recordType="plans" recordId={row.plan_id} busy={busy} save={save} />
          {row.alternative_beds.length > 0 && <div className="succession-alternatives"><p>Druga možnost: prazna greda enakih mer, preverjena glede kolobarja. Datumi ostanejo isti.</p>
            {row.alternative_beds.map(bed => <button type="button" className="secondary-button" disabled={busy} key={bed.id}
              onClick={() => change(`/api/planning/successions/plans/${row.plan_id}/move`, "POST", { bed_id: bed.id })}>PRESTAVI NA {bed.name}</button>)}
          </div>}
        </article>)}
        {group.change_count > 0 && <button type="button" className="primary-button" disabled={busy || !group.can_apply}
          onClick={() => change(`/api/planning/successions/${group.bed_id}/apply`, "POST", {})}>UPORABI {group.change_count} {group.change_count === 1 ? "PREMIK" : "PREMIKOV"} NA GREDI {group.bed}</button>}
      </details>)}
    </>}
  </section>;
}
