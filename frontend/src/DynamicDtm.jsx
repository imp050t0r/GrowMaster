import React, { useEffect, useState } from "react";
import { apiRequest } from "./platform";
import "./dynamicDtm.css";

export function DynamicDtm({ prediction, recordType, recordId, canRefresh = true }) {
  const [value, setValue] = useState(prediction);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setValue(prediction); setError(""); }, [prediction, recordType, recordId]);

  async function calculate() {
    setBusy(true);
    setError("");
    try {
      const result = await apiRequest(`/api/${recordType}/${recordId}/dynamic-dtm`, {
        method: "POST", body: JSON.stringify({}),
      });
      setValue(result.dynamic_dtm);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="dynamic-dtm" aria-label="Dinamična napoved žetve">
    {value ? <>
      <strong>Dynamic DTM: {value.dynamic_dtm_days} dni</strong>
      <span>Katalog: {value.catalog_dtm_days} dni · od {value.reference_kind === "transplant" ? "presajanja" : "setve"} {value.reference_date}</span>
      <span>Okvir žetve: {value.predicted_harvest_start} – {value.predicted_harvest_end}</span>
      <small>Zanesljivost: {value.confidence === "medium" ? "srednja" : "nizka"} · {value.fallback ? "sezonska ocena brez lokalne vremenske napovedi" : "GDD ocena"}</small>
      {value.history_correction && <small>Potrjeni zgodovinski popravek: {value.history_correction.days > 0 ? "+" : ""}{value.history_correction.days} dni · samo za ta načrt</small>}
      <details><summary>Kako je izračunano</summary>
        <ul>{value.reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul>
        <p>Obstoječi načrtovani datum žetve ostane ohranjen.</p>
      </details>
    </> : <>
      <span>Dynamic DTM še ni izračunan.</span>
      {canRefresh && <button type="button" className="secondary-button" disabled={busy} onClick={calculate}>{busy ? "Računam …" : "IZRAČUNAJ OCENO"}</button>}
    </>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
