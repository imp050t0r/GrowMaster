import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const today = new Date().toISOString().slice(0, 10);

function App() {
  const [crops, setCrops] = useState([]);
  const [beds, setBeds] = useState([]);
  const [plantings, setPlantings] = useState([]);
  const [form, setForm] = useState({ crop_id: "", variety_id: "", bed_id: "", sowing_date: today });
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [rotationWarning, setRotationWarning] = useState(null);

  const selectedCrop = useMemo(
    () => crops.find((crop) => String(crop.id) === String(form.crop_id)),
    [crops, form.crop_id],
  );

  async function loadData() {
    const [cropResponse, bedResponse, plantingResponse] = await Promise.all([
      fetch(`${API_URL}/api/crops`),
      fetch(`${API_URL}/api/beds`),
      fetch(`${API_URL}/api/plantings`),
    ]);
    if (!cropResponse.ok || !bedResponse.ok || !plantingResponse.ok) {
      throw new Error("Podatkov ni bilo mogoče naložiti.");
    }
    const [cropData, bedData, plantingData] = await Promise.all([
      cropResponse.json(),
      bedResponse.json(),
      plantingResponse.json(),
    ]);
    setCrops(cropData);
    setBeds(bedData);
    setPlantings(plantingData);
    setForm((current) => {
      const cropId = current.crop_id || cropData[0]?.id || "";
      const crop = cropData.find((item) => String(item.id) === String(cropId));
      return {
        ...current,
        crop_id: cropId,
        variety_id: current.variety_id || crop?.varieties[0]?.id || "",
        bed_id: current.bed_id || bedData[0]?.id || "",
      };
    });
  }

  useEffect(() => {
    loadData().catch((loadError) => setError(loadError.message));
  }, []);

  function changeCrop(event) {
    const cropId = event.target.value;
    const crop = crops.find((item) => String(item.id) === String(cropId));
    setForm((current) => ({
      ...current,
      crop_id: cropId,
      variety_id: crop?.varieties[0]?.id || "",
    }));
    setRotationWarning(null);
  }

  async function savePlanting(overrideRotation = false) {
    setError("");
    setNotice("");
    const response = await fetch(`${API_URL}/api/plantings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        crop_id: Number(form.crop_id),
        variety_id: Number(form.variety_id),
        bed_id: Number(form.bed_id),
        sowing_date: form.sowing_date,
        override_rotation: overrideRotation,
      }),
    });
    const data = await response.json();

    if (!response.ok) {
      const detail = data.detail;
      if (response.status === 409 && detail?.code === "ROTATION_WARNING") {
        setRotationWarning(detail);
        return;
      }
      setError(typeof detail === "string" ? detail : detail?.message || "Setve ni bilo mogoče shraniti.");
      return;
    }

    setRotationWarning(null);
    setNotice(data.message);
    await loadData();
  }

  function submit(event) {
    event.preventDefault();
    savePlanting(false).catch(() => setError("Povezava z API ni uspela."));
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Lokalno upravljanje kmetije</p>
          <h1>🌱 GrowMaster</h1>
          <p>Setev se po potrditvi samodejno poveže z izbrano gredico.</p>
        </div>
        <span className="status-pill">MVP 0.1</span>
      </header>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Načrt setve</p>
            <h2>Dodaj novo setev</h2>
          </div>
        </div>

        <form className="planting-form" onSubmit={submit}>
          <label>
            Kultura
            <select value={form.crop_id} onChange={changeCrop} required>
              {crops.map((crop) => <option key={crop.id} value={crop.id}>{crop.name}</option>)}
            </select>
          </label>

          <label>
            Sorta
            <select
              value={form.variety_id}
              onChange={(event) => setForm({ ...form, variety_id: event.target.value })}
              required
            >
              {(selectedCrop?.varieties || []).map((variety) => (
                <option key={variety.id} value={variety.id}>
                  {variety.name} · {variety.days_to_harvest} dni
                </option>
              ))}
            </select>
          </label>

          <label>
            Datum setve
            <input
              type="date"
              value={form.sowing_date}
              onChange={(event) => setForm({ ...form, sowing_date: event.target.value })}
              required
            />
          </label>

          <label>
            Gredica
            <select
              value={form.bed_id}
              onChange={(event) => {
                setForm({ ...form, bed_id: event.target.value });
                setRotationWarning(null);
              }}
              required
            >
              {beds.map((bed) => (
                <option key={bed.id} value={bed.id}>
                  {bed.name} · {bed.status === "empty" ? "prazna" : "zasedena"} · {bed.area_m2} m²
                </option>
              ))}
            </select>
          </label>

          <button className="primary-button" type="submit">DODAJ SETEV</button>
        </form>

        {notice && <div className="message success">✓ {notice}</div>}
        {error && <div className="message error">⚠ {error}</div>}
        {rotationWarning && (
          <div className="rotation-warning">
            <strong>Opozorilo kolobarja</strong>
            <p>{rotationWarning.message}</p>
            <p>{rotationWarning.warnings?.[0]}</p>
            <div className="warning-actions">
              <button type="button" onClick={() => setRotationWarning(null)}>IZBERI DRUGO GREDICO</button>
              <button type="button" className="danger-button" onClick={() => savePlanting(true)}>VSEENO POSEJ</button>
            </div>
          </div>
        )}
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Stanje na terenu</p>
            <h2>Gredice</h2>
          </div>
          <span>{beds.length} skupaj</span>
        </div>
        <div className="bed-grid">
          {beds.map((bed) => (
            <article className="bed-card" key={bed.id}>
              <div className="bed-card-top">
                <h3>{bed.name}</h3>
                <span className={`bed-status ${bed.status}`}>{bed.status === "empty" ? "Prazna" : "Raste"}</span>
              </div>
              <p>{bed.width_m} × {bed.length_m} m · <strong>{bed.area_m2} m²</strong></p>
              {bed.current_planting ? (
                <div className="crop-block">
                  <strong>{bed.current_planting.crop} {bed.current_planting.variety}</strong>
                  <span>Setev: {bed.current_planting.sowing_date}</span>
                  <span>Žetev: {bed.current_planting.expected_harvest_date}</span>
                </div>
              ) : (
                <p className="muted">Pripravljena za novo setev.</p>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Aktivni rastni cikli</p>
            <h2>Setve</h2>
          </div>
          <span>{plantings.length} aktivnih</span>
        </div>
        {plantings.length === 0 ? (
          <p className="empty-state">Prva setev še ni dodana.</p>
        ) : (
          <div className="planting-list">
            {plantings.map((planting) => (
              <article key={planting.id}>
                <strong>{planting.bed} · {planting.crop} {planting.variety}</strong>
                <span>{planting.sowing_date} → {planting.expected_harvest_date}</span>
                {planting.rotation_override && <small>Kolobar je uporabnik zavestno preglasil.</small>}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
