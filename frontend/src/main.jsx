import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const now = new Date();
const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;

const taskTypeLabels = {
  general: "Splošno",
  inspection: "Pregled",
  irrigation: "Namakanje",
  bed_preparation: "Priprava gredice",
  emergence_check: "Pregled vznika",
  growth_check: "Pregled rasti",
  harvest_check: "Kontrola žetve",
};

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message || "Zahteva ni uspela.");
  }
  return data;
}

function App() {
  const [view, setView] = useState("dashboard");
  const [crops, setCrops] = useState([]);
  const [beds, setBeds] = useState([]);
  const [plantings, setPlantings] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [taskDate, setTaskDate] = useState(today);
  const [selectedBed, setSelectedBed] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [rotationWarning, setRotationWarning] = useState(null);
  const [completionTaskId, setCompletionTaskId] = useState(null);

  const [plantingForm, setPlantingForm] = useState({
    crop_id: "",
    variety_id: "",
    bed_id: "",
    sowing_date: today,
  });
  const [bedForm, setBedForm] = useState({ name: "", width_m: "0.8", length_m: "15" });
  const [taskForm, setTaskForm] = useState({
    title: "",
    task_type: "general",
    due_date: today,
    bed_id: "",
    priority: "normal",
  });
  const [completion, setCompletion] = useState({
    duration_minutes: "",
    quantity_used: "",
    unit: "",
    notes: "",
  });

  const selectedCrop = useMemo(
    () => crops.find((crop) => String(crop.id) === String(plantingForm.crop_id)),
    [crops, plantingForm.crop_id],
  );

  async function loadData() {
    const [cropData, bedData, plantingData, taskData, dashboardData] = await Promise.all([
      apiRequest("/api/crops"),
      apiRequest("/api/beds"),
      apiRequest("/api/plantings"),
      apiRequest(`/api/tasks?date=${taskDate}`),
      apiRequest(`/api/dashboard?date=${today}`),
    ]);
    setCrops(cropData);
    setBeds(bedData);
    setPlantings(plantingData);
    setTasks(taskData);
    setDashboard(dashboardData);
    setPlantingForm((current) => {
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
  }, [taskDate]);

  function clearMessages() {
    setNotice("");
    setError("");
  }

  function changeCrop(event) {
    const cropId = event.target.value;
    const crop = crops.find((item) => String(item.id) === String(cropId));
    setPlantingForm((current) => ({
      ...current,
      crop_id: cropId,
      variety_id: crop?.varieties[0]?.id || "",
    }));
    setRotationWarning(null);
  }

  async function savePlanting(overrideRotation = false) {
    clearMessages();
    const response = await fetch(`${API_URL}/api/plantings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        crop_id: Number(plantingForm.crop_id),
        variety_id: Number(plantingForm.variety_id),
        bed_id: Number(plantingForm.bed_id),
        sowing_date: plantingForm.sowing_date,
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
    setView("beds");
  }

  async function createBed(event) {
    event.preventDefault();
    clearMessages();
    try {
      const data = await apiRequest("/api/beds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: bedForm.name,
          width_m: Number(bedForm.width_m),
          length_m: Number(bedForm.length_m),
        }),
      });
      setBedForm({ name: "", width_m: "0.8", length_m: "15" });
      setNotice(`Gredica ${data.name} je dodana.`);
      await loadData();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function openBed(bedId) {
    clearMessages();
    try {
      const detail = await apiRequest(`/api/beds/${bedId}`);
      setSelectedBed(detail);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function finishPlanting(plantingId) {
    if (!window.confirm("Zaključim rastni cikel in sprostim gredico?")) return;
    clearMessages();
    try {
      const data = await apiRequest(`/api/plantings/${plantingId}/finish`, { method: "POST" });
      setNotice(data.message);
      setSelectedBed(null);
      await loadData();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function createTask(event) {
    event.preventDefault();
    clearMessages();
    try {
      const data = await apiRequest("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: taskForm.title,
          task_type: taskForm.task_type,
          due_date: taskForm.due_date,
          bed_id: taskForm.bed_id ? Number(taskForm.bed_id) : null,
          priority: taskForm.priority,
        }),
      });
      setTaskForm({ title: "", task_type: "general", due_date: taskDate, bed_id: "", priority: "normal" });
      setNotice(data.message);
      setTaskDate(data.due_date);
      await loadData();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function completeTask(event, taskId) {
    event.preventDefault();
    clearMessages();
    try {
      const data = await apiRequest(`/api/tasks/${taskId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          duration_minutes: completion.duration_minutes ? Number(completion.duration_minutes) : null,
          quantity_used: completion.quantity_used ? Number(completion.quantity_used) : null,
          unit: completion.unit || null,
          notes: completion.notes || null,
        }),
      });
      setCompletionTaskId(null);
      setCompletion({ duration_minutes: "", quantity_used: "", unit: "", notes: "" });
      setNotice(data.message);
      await loadData();
      if (selectedBed?.id) await openBed(selectedBed.id);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  const navigation = [
    ["dashboard", "Domov", "⌂"],
    ["beds", "Gredice", "▦"],
    ["planting", "Setev", "+"],
    ["tasks", "Opravila", "✓"],
  ];

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Lokalno upravljanje kmetije</p>
          <h1>🌱 GrowMaster</h1>
          <p>Gredice, setve in dnevno delo na enem mestu.</p>
        </div>
        <span className="status-pill">MVP 0.2</span>
      </header>

      <nav className="main-nav" aria-label="Glavna navigacija">
        {navigation.map(([key, label, icon]) => (
          <button key={key} className={view === key ? "active" : ""} onClick={() => setView(key)}>
            <span>{icon}</span>{label}
          </button>
        ))}
      </nav>

      {notice && <div className="message success">✓ {notice}</div>}
      {error && <div className="message error">⚠ {error}</div>}

      {view === "dashboard" && (
        <DashboardView dashboard={dashboard} beds={beds} setView={setView} />
      )}

      {view === "beds" && (
        <BedsView
          beds={beds}
          bedForm={bedForm}
          setBedForm={setBedForm}
          createBed={createBed}
          openBed={openBed}
          selectedBed={selectedBed}
          setSelectedBed={setSelectedBed}
          finishPlanting={finishPlanting}
        />
      )}

      {view === "planting" && (
        <PlantingView
          crops={crops}
          beds={beds}
          plantings={plantings}
          form={plantingForm}
          setForm={setPlantingForm}
          selectedCrop={selectedCrop}
          changeCrop={changeCrop}
          savePlanting={savePlanting}
          rotationWarning={rotationWarning}
          setRotationWarning={setRotationWarning}
        />
      )}

      {view === "tasks" && (
        <TasksView
          tasks={tasks}
          beds={beds}
          taskDate={taskDate}
          setTaskDate={setTaskDate}
          taskForm={taskForm}
          setTaskForm={setTaskForm}
          createTask={createTask}
          completionTaskId={completionTaskId}
          setCompletionTaskId={setCompletionTaskId}
          completion={completion}
          setCompletion={setCompletion}
          completeTask={completeTask}
        />
      )}
    </main>
  );
}

function DashboardView({ dashboard, beds, setView }) {
  const emptyBeds = beds.filter((bed) => bed.status === "empty").length;
  return (
    <>
      <section className="metric-grid">
        <article className="metric-card"><span>Današnja opravila</span><strong>{dashboard?.tasks_total || 0}</strong><small>{dashboard?.tasks_completed || 0} opravljenih</small></article>
        <article className="metric-card"><span>Aktivne gredice</span><strong>{dashboard?.active_beds || 0}</strong><small>{emptyBeds} praznih</small></article>
        <article className="metric-card"><span>Naslednja žetev</span><strong>{dashboard?.next_harvest?.bed || "—"}</strong><small>{dashboard?.next_harvest ? `${dashboard.next_harvest.crop} · ${dashboard.next_harvest.expected_harvest_date}` : "Ni aktivnih setev"}</small></article>
      </section>
      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">Danes</p><h2>Terensko delo</h2></div><button className="text-button" onClick={() => setView("tasks")}>Vsa opravila →</button></div>
        <div className="task-list compact">
          {(dashboard?.tasks || []).map((task) => <TaskSummary key={task.id} task={task} />)}
          {!dashboard?.tasks?.length && <p className="empty-state">Za danes ni opravil.</p>}
        </div>
      </section>
    </>
  );
}

function BedsView({ beds, bedForm, setBedForm, createBed, openBed, selectedBed, setSelectedBed, finishPlanting }) {
  return (
    <>
      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">Nova lokacija</p><h2>Dodaj gredico</h2></div></div>
        <form className="inline-form" onSubmit={createBed}>
          <label>Ime<input value={bedForm.name} onChange={(event) => setBedForm({ ...bedForm, name: event.target.value })} placeholder="A7" required /></label>
          <label>Širina (m)<input type="number" step="0.01" min="0.1" value={bedForm.width_m} onChange={(event) => setBedForm({ ...bedForm, width_m: event.target.value })} required /></label>
          <label>Dolžina (m)<input type="number" step="0.1" min="0.1" value={bedForm.length_m} onChange={(event) => setBedForm({ ...bedForm, length_m: event.target.value })} required /></label>
          <button className="primary-button" type="submit">DODAJ GREDICO</button>
        </form>
      </section>

      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">Stanje na terenu</p><h2>Gredice</h2></div><span>{beds.length} skupaj</span></div>
        <div className="bed-grid">
          {beds.map((bed) => (
            <button className="bed-card" key={bed.id} onClick={() => openBed(bed.id)}>
              <div className="bed-card-top"><h3>{bed.name}</h3><span className={`bed-status ${bed.status}`}>{bed.status === "empty" ? "Prazna" : "Raste"}</span></div>
              <p>{bed.width_m} × {bed.length_m} m · <strong>{bed.area_m2} m²</strong></p>
              {bed.current_planting ? (
                <div className="crop-block"><strong>{bed.current_planting.crop} {bed.current_planting.variety}</strong><span>Setev: {bed.current_planting.sowing_date}</span><span>Žetev: {bed.current_planting.expected_harvest_date}</span></div>
              ) : <p className="muted">Pripravljena za novo setev.</p>}
              {bed.has_open_tasks && <small className="task-flag">● odprto opravilo</small>}
            </button>
          ))}
        </div>
      </section>

      {selectedBed && (
        <section className="panel bed-detail">
          <div className="section-heading"><div><p className="eyebrow">Podrobnosti gredice</p><h2>{selectedBed.name} · {selectedBed.area_m2} m²</h2></div><button className="icon-button" onClick={() => setSelectedBed(null)}>✕</button></div>
          {selectedBed.current_planting ? (
            <div className="current-cycle"><div><span>Trenutno raste</span><strong>{selectedBed.current_planting.crop} {selectedBed.current_planting.variety}</strong><small>{selectedBed.current_planting.sowing_date} → {selectedBed.current_planting.expected_harvest_date}</small></div><button className="secondary-button" onClick={() => finishPlanting(selectedBed.current_planting.id)}>ZAKLJUČI CIKEL</button></div>
          ) : <div className="empty-state-box">Gredica je prazna in pripravljena za setev.</div>}
          <div className="detail-columns">
            <div><h3>Zgodovina</h3>{selectedBed.history.length ? selectedBed.history.map((item) => <div className="history-row" key={item.id}><strong>{item.crop} {item.variety}</strong><span>{item.sowing_date} · {item.status === "active" ? "aktivno" : "zaključeno"}</span></div>) : <p className="muted">Zgodovine še ni.</p>}</div>
            <div><h3>Opravila gredice</h3>{selectedBed.tasks.length ? selectedBed.tasks.map((task) => <TaskSummary key={task.id} task={task} />) : <p className="muted">Ni vezanih opravil.</p>}</div>
          </div>
        </section>
      )}
    </>
  );
}

function PlantingView({ crops, beds, plantings, form, setForm, selectedCrop, changeCrop, savePlanting, rotationWarning, setRotationWarning }) {
  return (
    <>
      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">Načrt setve</p><h2>Dodaj novo setev</h2></div></div>
        <form className="planting-form" onSubmit={(event) => { event.preventDefault(); savePlanting(false); }}>
          <label>Kultura<select value={form.crop_id} onChange={changeCrop} required>{crops.map((crop) => <option key={crop.id} value={crop.id}>{crop.name}</option>)}</select></label>
          <label>Sorta<select value={form.variety_id} onChange={(event) => setForm({ ...form, variety_id: event.target.value })} required>{(selectedCrop?.varieties || []).map((variety) => <option key={variety.id} value={variety.id}>{variety.name} · {variety.days_to_harvest} dni</option>)}</select></label>
          <label>Datum setve<input type="date" value={form.sowing_date} onChange={(event) => setForm({ ...form, sowing_date: event.target.value })} required /></label>
          <label>Gredica<select value={form.bed_id} onChange={(event) => { setForm({ ...form, bed_id: event.target.value }); setRotationWarning(null); }} required>{beds.map((bed) => <option key={bed.id} value={bed.id}>{bed.name} · {bed.status === "empty" ? "prazna" : "zasedena"} · {bed.area_m2} m²</option>)}</select></label>
          <button className="primary-button" type="submit">DODAJ SETEV</button>
        </form>
        {rotationWarning && <div className="rotation-warning"><strong>Opozorilo kolobarja</strong><p>{rotationWarning.message}</p><p>{rotationWarning.warnings?.[0]}</p><div className="warning-actions"><button type="button" onClick={() => setRotationWarning(null)}>IZBERI DRUGO GREDICO</button><button type="button" className="danger-button" onClick={() => savePlanting(true)}>VSEENO POSEJ</button></div></div>}
      </section>
      <section className="panel"><div className="section-heading"><div><p className="eyebrow">Aktivni rastni cikli</p><h2>Setve</h2></div><span>{plantings.length} aktivnih</span></div>{plantings.length === 0 ? <p className="empty-state">Prva setev še ni dodana.</p> : <div className="planting-list">{plantings.map((planting) => <article key={planting.id}><strong>{planting.bed} · {planting.crop} {planting.variety}</strong><span>{planting.sowing_date} → {planting.expected_harvest_date}</span>{planting.rotation_override && <small>Kolobar je uporabnik zavestno preglasil.</small>}</article>)}</div>}</section>
    </>
  );
}

function TasksView({ tasks, beds, taskDate, setTaskDate, taskForm, setTaskForm, createTask, completionTaskId, setCompletionTaskId, completion, setCompletion, completeTask }) {
  return (
    <>
      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">Novo delo</p><h2>Dodaj opravilo</h2></div></div>
        <form className="task-form" onSubmit={createTask}>
          <label className="wide">Opravilo<input value={taskForm.title} onChange={(event) => setTaskForm({ ...taskForm, title: event.target.value })} placeholder="Npr. zalivanje A1–A6" required /></label>
          <label>Vrsta<select value={taskForm.task_type} onChange={(event) => setTaskForm({ ...taskForm, task_type: event.target.value })}>{Object.entries(taskTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>Datum<input type="date" value={taskForm.due_date} onChange={(event) => setTaskForm({ ...taskForm, due_date: event.target.value })} required /></label>
          <label>Gredica<select value={taskForm.bed_id} onChange={(event) => setTaskForm({ ...taskForm, bed_id: event.target.value })}><option value="">Vse / brez gredice</option>{beds.map((bed) => <option key={bed.id} value={bed.id}>{bed.name}</option>)}</select></label>
          <label>Prioriteta<select value={taskForm.priority} onChange={(event) => setTaskForm({ ...taskForm, priority: event.target.value })}><option value="low">Nizka</option><option value="normal">Normalna</option><option value="high">Visoka</option></select></label>
          <button className="primary-button" type="submit">DODAJ OPRAVILO</button>
        </form>
      </section>

      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">Dnevni center</p><h2>Opravila</h2></div><label className="date-filter">Datum<input type="date" value={taskDate} onChange={(event) => setTaskDate(event.target.value)} /></label></div>
        <div className="task-list">
          {tasks.map((task) => (
            <article className={`task-card ${task.status}`} key={task.id}>
              <div className="task-main"><span className={`priority-dot ${task.priority}`}></span><div><strong>{task.title}</strong><span>{taskTypeLabels[task.task_type] || task.task_type}{task.bed ? ` · gredica ${task.bed}` : ""}</span></div><span className={`task-state ${task.status}`}>{task.status === "completed" ? "Opravljeno" : "Načrtovano"}</span></div>
              {task.status !== "completed" && completionTaskId !== task.id && <button className="secondary-button" onClick={() => setCompletionTaskId(task.id)}>ZAKLJUČI</button>}
              {completionTaskId === task.id && (
                <form className="completion-form" onSubmit={(event) => completeTask(event, task.id)}>
                  <label>Trajanje (min)<input type="number" min="0" value={completion.duration_minutes} onChange={(event) => setCompletion({ ...completion, duration_minutes: event.target.value })} /></label>
                  <label>Poraba<input type="number" min="0" step="0.01" value={completion.quantity_used} onChange={(event) => setCompletion({ ...completion, quantity_used: event.target.value })} /></label>
                  <label>Enota<input value={completion.unit} onChange={(event) => setCompletion({ ...completion, unit: event.target.value })} placeholder="L, kg, kos" /></label>
                  <label className="wide">Opomba<input value={completion.notes} onChange={(event) => setCompletion({ ...completion, notes: event.target.value })} placeholder="Kaj je bilo narejeno?" /></label>
                  <div className="completion-actions"><button type="button" className="text-button" onClick={() => setCompletionTaskId(null)}>PREKLIČI</button><button className="primary-button" type="submit">POTRDI OPRAVLJENO</button></div>
                </form>
              )}
              {task.status === "completed" && <div className="completion-summary">{task.duration_minutes != null && <span>{task.duration_minutes} min</span>}{task.quantity_used != null && <span>{task.quantity_used} {task.unit || ""}</span>}{task.notes && <span>{task.notes}</span>}</div>}
            </article>
          ))}
          {!tasks.length && <p className="empty-state">Za izbrani datum ni opravil.</p>}
        </div>
      </section>
    </>
  );
}

function TaskSummary({ task }) {
  return <div className={`task-summary ${task.status}`}><span className={`priority-dot ${task.priority}`}></span><div><strong>{task.title}</strong><small>{task.bed ? `Gredica ${task.bed}` : taskTypeLabels[task.task_type] || "Splošno"}</small></div><span>{task.status === "completed" ? "✓" : task.due_date}</span></div>;
}

createRoot(document.getElementById("root")).render(<React.StrictMode><App /></React.StrictMode>);
