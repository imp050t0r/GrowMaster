import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const now = new Date();
const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
const inDays = (days) => {
  const value = new Date(now); value.setDate(value.getDate() + days);
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
};

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
  const [harvests, setHarvests] = useState([]);
  const [economics, setEconomics] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [document, setDocument] = useState(null);
  const [plans, setPlans] = useState([]);
  const [planningCalendar, setPlanningCalendar] = useState([]);
  const [forecast, setForecast] = useState({ rows: [], warnings: [] });
  const [retailSales, setRetailSales] = useState([]);
  const [salesSettings, setSalesSettings] = useState(null);
  const [salesReport, setSalesReport] = useState({ summary: {}, daily: [], entries: [], note: "" });
  const [receivables, setReceivables] = useState({ summary: {}, items: [], note: "" });
  const [reportStart, setReportStart] = useState(today);
  const [reportEnd, setReportEnd] = useState(today);
  const [receivablesAsOf, setReceivablesAsOf] = useState(today);
  const [includePaidReceivables, setIncludePaidReceivables] = useState(false);
  const [paymentOrderId, setPaymentOrderId] = useState(null);
  const [planStart, setPlanStart] = useState(today);
  const [planEnd, setPlanEnd] = useState(inDays(90));
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
  const [harvestForm, setHarvestForm] = useState({ planting_id: "", harvest_date: today, quantity_kg: "", quality: "A", notes: "" });
  const [costForm, setCostForm] = useState({ bed_id: "", planting_id: "", cost_date: today, category: "labor", amount_eur: "", description: "" });
  const [saleForm, setSaleForm] = useState({ harvest_id: "", sale_date: today, quantity_kg: "", price_per_kg_eur: "", customer: "" });
  const [customerForm, setCustomerForm] = useState({ name: "", email: "", phone: "", address: "", customer_type: "consumer", tax_number: "" });
  const [orderForm, setOrderForm] = useState({ customer_id: "", harvest_id: "", order_date: today, delivery_date: today, quantity_kg: "", price_per_kg_eur: "", notes: "" });
  const [planForm, setPlanForm] = useState({ bed_id: "", crop_id: "", variety_id: "", sowing_date: today, transplant_date: "", expected_yield_kg: "", succession_count: "1", succession_interval_days: "14", notes: "" });
  const [quickSaleForm, setQuickSaleForm] = useState({ customer_id: "", harvest_id: "", sale_date: today, payment_method: "cash", quantity_kg: "", price_per_kg_eur: "" });
  const [paymentForm, setPaymentForm] = useState({ payment_date: today, amount_eur: "", payment_method: "bank_transfer", notes: "" });

  const selectedCrop = useMemo(
    () => crops.find((crop) => String(crop.id) === String(plantingForm.crop_id)),
    [crops, plantingForm.crop_id],
  );
  const selectedPlanCrop = useMemo(
    () => crops.find((crop) => String(crop.id) === String(planForm.crop_id)),
    [crops, planForm.crop_id],
  );

  async function loadData() {
    const [cropData, bedData, plantingData, taskData, dashboardData, harvestData, economicsData, inventoryData, customerData, orderData, planData, calendarData, forecastData, retailSaleData, salesSettingsData, salesReportData, receivablesData] = await Promise.all([
      apiRequest("/api/crops"),
      apiRequest("/api/beds"),
      apiRequest("/api/plantings"),
      apiRequest(`/api/tasks?date=${taskDate}`),
      apiRequest(`/api/dashboard?date=${today}`),
      apiRequest("/api/harvests"),
      apiRequest("/api/economics/by-bed"),
      apiRequest("/api/inventory"),
      apiRequest("/api/customers"),
      apiRequest("/api/orders"),
      apiRequest("/api/plans"),
      apiRequest(`/api/planning/calendar?start=${planStart}&end=${planEnd}`),
      apiRequest(`/api/planning/forecast?start=${planStart}&end=${planEnd}`),
      apiRequest("/api/retail-sales"),
      apiRequest("/api/sales-settings"),
      apiRequest(`/api/sales-report?start=${reportStart}&end=${reportEnd}`),
      apiRequest(`/api/receivables?as_of=${receivablesAsOf}&include_paid=${includePaidReceivables}`),
    ]);
    setCrops(cropData);
    setBeds(bedData);
    setPlantings(plantingData);
    setTasks(taskData);
    setDashboard(dashboardData);
    setHarvests(harvestData);
    setEconomics(economicsData);
    setInventory(inventoryData);
    setCustomers(customerData);
    setOrders(orderData);
    setPlans(planData);
    setPlanningCalendar(calendarData.events);
    setForecast(forecastData);
    setRetailSales(retailSaleData);
    setSalesSettings(salesSettingsData);
    setSalesReport(salesReportData);
    setReceivables(receivablesData);
    setHarvestForm((current) => ({ ...current, planting_id: current.planting_id || plantingData[0]?.id || "" }));
    setCostForm((current) => ({ ...current, bed_id: current.bed_id || bedData[0]?.id || "" }));
    setSaleForm((current) => ({ ...current, harvest_id: current.harvest_id || harvestData.find((item) => item.available_kg > 0)?.id || "" }));
    setOrderForm((current) => ({
      ...current,
      customer_id: current.customer_id || customerData[0]?.id || "",
      harvest_id: current.harvest_id || inventoryData.find((item) => item.available_kg > 0)?.harvest_id || "",
    }));
    setQuickSaleForm((current) => ({ ...current, harvest_id: current.harvest_id || inventoryData.find((item) => item.available_kg > 0)?.harvest_id || "" }));
    setPlanForm((current) => {
      const cropId = current.crop_id || cropData[0]?.id || "";
      const crop = cropData.find((item) => String(item.id) === String(cropId));
      return { ...current, bed_id: current.bed_id || bedData[0]?.id || "", crop_id: cropId, variety_id: current.variety_id || crop?.varieties[0]?.id || "" };
    });
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
  }, [taskDate, planStart, planEnd, reportStart, reportEnd, receivablesAsOf, includePaidReceivables]);

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

  async function submitEconomics(event, path, payload, reset) {
    event.preventDefault();
    clearMessages();
    try {
      const data = await apiRequest(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      setNotice(data.message);
      reset();
      await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function createCustomer(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/customers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(customerForm) });
      setCustomerForm({ name: "", email: "", phone: "", address: "", customer_type: "consumer", tax_number: "" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function createOrder(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ customer_id: Number(orderForm.customer_id), order_date: orderForm.order_date, delivery_date: orderForm.delivery_date, notes: orderForm.notes || null, items: [{ harvest_id: Number(orderForm.harvest_id), quantity_kg: Number(orderForm.quantity_kg), price_per_kg_eur: Number(orderForm.price_per_kg_eur) }] }) });
      setOrderForm({ ...orderForm, quantity_kg: "", price_per_kg_eur: "", notes: "" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function changeOrderStatus(orderId, status) {
    if (!window.confirm(status === "fulfilled" ? "Potrdim dostavo in zabeležim prodajo?" : "Prekličem naročilo in sprostim zalogo?")) return;
    clearMessages();
    try {
      const data = await apiRequest(`/api/orders/${orderId}/status`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) });
      setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function openOrderDocument(orderId, type) {
    clearMessages();
    try { setDocument(await apiRequest(`/api/orders/${orderId}/document?document_type=${type}`)); }
    catch (requestError) { setError(requestError.message); }
  }

  async function createQuickSale(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/retail-sales", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ customer_id: quickSaleForm.customer_id ? Number(quickSaleForm.customer_id) : null, sale_date: quickSaleForm.sale_date, payment_method: quickSaleForm.payment_method, items: [{ harvest_id: Number(quickSaleForm.harvest_id), quantity_kg: Number(quickSaleForm.quantity_kg), price_per_kg_eur: Number(quickSaleForm.price_per_kg_eur) }] }) });
      setQuickSaleForm({ ...quickSaleForm, quantity_kg: "", price_per_kg_eur: "" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function openRetailDocument(saleId, type) {
    clearMessages();
    try { setDocument(await apiRequest(`/api/retail-sales/${saleId}/document?document_type=${type}`)); }
    catch (requestError) { setError(requestError.message); }
  }

  async function saveSalesSettings(event) {
    event.preventDefault(); clearMessages();
    try { const data = await apiRequest("/api/sales-settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(salesSettings) }); setNotice(data.message); await loadData(); }
    catch (requestError) { setError(requestError.message); }
  }

  async function recordPayment(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest(`/api/orders/${paymentOrderId}/payments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...paymentForm, amount_eur: Number(paymentForm.amount_eur) }) });
      setPaymentOrderId(null); setPaymentForm({ payment_date: today, amount_eur: "", payment_method: "bank_transfer", notes: "" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  function beginPayment(item) {
    clearMessages();
    setPaymentOrderId(item.order_id);
    setPaymentForm({ payment_date: today < item.delivery_date ? item.delivery_date : today, amount_eur: item.outstanding_eur.toFixed(2), payment_method: "bank_transfer", notes: "" });
  }

  function changePlanCrop(event) {
    const cropId = event.target.value;
    const crop = crops.find((item) => String(item.id) === String(cropId));
    setPlanForm({ ...planForm, crop_id: cropId, variety_id: crop?.varieties[0]?.id || "" });
  }

  async function createPlan(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/plans", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...planForm, bed_id: Number(planForm.bed_id), crop_id: Number(planForm.crop_id), variety_id: Number(planForm.variety_id), transplant_date: planForm.transplant_date || null, expected_yield_kg: Number(planForm.expected_yield_kg), succession_count: Number(planForm.succession_count), succession_interval_days: Number(planForm.succession_interval_days), notes: planForm.notes || null }) });
      setNotice(`${data.message}${data.warnings.length ? ` Opozorila: ${data.warnings.join(" ")}` : ""}`);
      setPlanForm({ ...planForm, expected_yield_kg: "", notes: "" }); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function activatePlan(planId, overrideRotation = false) {
    clearMessages();
    const response = await fetch(`${API_URL}/api/plans/${planId}/activate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ override_rotation: overrideRotation }) });
    const data = await response.json();
    if (!response.ok) {
      const detail = data.detail;
      if (detail?.code === "ROTATION_WARNING" && !overrideRotation && window.confirm(`${detail.message}\n\nVseeno aktiviram setev?`)) return activatePlan(planId, true);
      setError(typeof detail === "string" ? detail : detail?.message || "Načrta ni mogoče aktivirati."); return;
    }
    setNotice(data.message); await loadData();
  }

  async function cancelPlan(planId) {
    if (!window.confirm("Prekličem načrtovano setev?")) return;
    clearMessages();
    try { const data = await apiRequest(`/api/plans/${planId}/status`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "cancelled" }) }); setNotice(data.message); await loadData(); }
    catch (requestError) { setError(requestError.message); }
  }

  const navigation = [
    ["dashboard", "Domov", "⌂"],
    ["beds", "Gredice", "▦"],
    ["planting", "Setev", "+"],
    ["tasks", "Opravila", "✓"],
    ["economics", "Žetev €", "€"],
    ["orders", "Naročila", "▤"],
    ["reports", "Prodaja", "Σ"],
    ["receivables", "Terjatve", "↔"],
    ["planning", "Plan", "◫"],
  ];

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Lokalno upravljanje kmetije</p>
          <h1>🌱 GrowMaster</h1>
          <p>Gredice, setve in dnevno delo na enem mestu.</p>
        </div>
        <span className="status-pill">MVP 0.8</span>
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
      {view === "economics" && (
        <EconomicsView
          beds={beds} plantings={plantings} harvests={harvests} economics={economics}
          harvestForm={harvestForm} setHarvestForm={setHarvestForm}
          costForm={costForm} setCostForm={setCostForm}
          saleForm={saleForm} setSaleForm={setSaleForm}
          submit={submitEconomics}
        />
      )}
      {view === "orders" && (
        <OrdersView inventory={inventory} customers={customers} orders={orders}
          customerForm={customerForm} setCustomerForm={setCustomerForm} createCustomer={createCustomer}
          orderForm={orderForm} setOrderForm={setOrderForm} createOrder={createOrder}
          changeOrderStatus={changeOrderStatus} openOrderDocument={openOrderDocument}
          document={document} setDocument={setDocument} retailSales={retailSales}
          quickSaleForm={quickSaleForm} setQuickSaleForm={setQuickSaleForm} createQuickSale={createQuickSale} openRetailDocument={openRetailDocument}
          salesSettings={salesSettings} setSalesSettings={setSalesSettings} saveSalesSettings={saveSalesSettings} />
      )}
      {view === "reports" && (
        <SalesReportView report={salesReport} start={reportStart} setStart={setReportStart} end={reportEnd} setEnd={setReportEnd} />
      )}
      {view === "receivables" && (
        <ReceivablesView data={receivables} asOf={receivablesAsOf} setAsOf={setReceivablesAsOf} includePaid={includePaidReceivables} setIncludePaid={setIncludePaidReceivables} paymentOrderId={paymentOrderId} beginPayment={beginPayment} cancelPayment={() => setPaymentOrderId(null)} paymentForm={paymentForm} setPaymentForm={setPaymentForm} recordPayment={recordPayment} />
      )}
      {view === "planning" && (
        <PlanningView crops={crops} beds={beds} plans={plans} calendar={planningCalendar} forecast={forecast}
          form={planForm} setForm={setPlanForm} selectedCrop={selectedPlanCrop} changeCrop={changePlanCrop} createPlan={createPlan}
          activatePlan={activatePlan} cancelPlan={cancelPlan} start={planStart} setStart={setPlanStart} end={planEnd} setEnd={setPlanEnd} />
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

function EconomicsView({ beds, plantings, harvests, economics, harvestForm, setHarvestForm, costForm, setCostForm, saleForm, setSaleForm, submit }) {
  const availableHarvests = harvests.filter((item) => item.available_kg > 0);
  return <>
    <section className="metric-grid economics-grid">
      <article className="metric-card"><span>Skupaj pridelano</span><strong>{economics.reduce((sum, item) => sum + item.harvested_kg, 0).toFixed(1)} kg</strong><small>evidentirana žetev</small></article>
      <article className="metric-card"><span>Prihodki</span><strong>{economics.reduce((sum, item) => sum + item.revenue_eur, 0).toFixed(2)} €</strong><small>zabeležena prodaja</small></article>
      <article className="metric-card"><span>Dobiček</span><strong>{economics.reduce((sum, item) => sum + item.profit_eur, 0).toFixed(2)} €</strong><small>prihodki − stroški</small></article>
    </section>
    <section className="economics-forms">
      <form className="panel compact-form" onSubmit={(event) => submit(event, "/api/harvests", { ...harvestForm, planting_id: Number(harvestForm.planting_id), quantity_kg: Number(harvestForm.quantity_kg) }, () => setHarvestForm({ ...harvestForm, quantity_kg: "", notes: "" }))}>
        <h2>Zabeleži žetev</h2>
        <label>Aktivna setev<select value={harvestForm.planting_id} onChange={(e) => setHarvestForm({ ...harvestForm, planting_id: e.target.value })} required>{plantings.map((p) => <option key={p.id} value={p.id}>{p.bed} · {p.crop} {p.variety}</option>)}</select></label>
        <label>Datum<input type="date" value={harvestForm.harvest_date} onChange={(e) => setHarvestForm({ ...harvestForm, harvest_date: e.target.value })} required /></label>
        <label>Količina (kg)<input type="number" min="0.01" step="0.01" value={harvestForm.quantity_kg} onChange={(e) => setHarvestForm({ ...harvestForm, quantity_kg: e.target.value })} required /></label>
        <label>Kakovost<select value={harvestForm.quality} onChange={(e) => setHarvestForm({ ...harvestForm, quality: e.target.value })}><option value="A">A – prva</option><option value="B">B – druga</option><option value="waste">Odpad</option></select></label>
        <button className="primary-button">SHRANI ŽETEV</button>
      </form>
      <form className="panel compact-form" onSubmit={(event) => submit(event, "/api/costs", { ...costForm, bed_id: Number(costForm.bed_id), planting_id: costForm.planting_id ? Number(costForm.planting_id) : null, amount_eur: Number(costForm.amount_eur) }, () => setCostForm({ ...costForm, amount_eur: "", description: "" }))}>
        <h2>Dodaj strošek</h2>
        <label>Gredica<select value={costForm.bed_id} onChange={(e) => setCostForm({ ...costForm, bed_id: e.target.value })} required>{beds.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
        <label>Kategorija<select value={costForm.category} onChange={(e) => setCostForm({ ...costForm, category: e.target.value })}><option value="labor">Delo</option><option value="seed">Seme</option><option value="fertilizer">Gnojilo</option><option value="water">Voda</option><option value="packaging">Embalaža</option><option value="other">Drugo</option></select></label>
        <label>Znesek (€)<input type="number" min="0.01" step="0.01" value={costForm.amount_eur} onChange={(e) => setCostForm({ ...costForm, amount_eur: e.target.value })} required /></label>
        <label>Opis<input value={costForm.description} onChange={(e) => setCostForm({ ...costForm, description: e.target.value })} required /></label>
        <button className="primary-button">SHRANI STROŠEK</button>
      </form>
      <form className="panel compact-form" onSubmit={(event) => submit(event, "/api/sales", { ...saleForm, harvest_id: Number(saleForm.harvest_id), quantity_kg: Number(saleForm.quantity_kg), price_per_kg_eur: Number(saleForm.price_per_kg_eur) }, () => setSaleForm({ ...saleForm, quantity_kg: "", price_per_kg_eur: "", customer: "" }))}>
        <h2>Zabeleži prodajo</h2>
        <label>Žetev<select value={saleForm.harvest_id} onChange={(e) => setSaleForm({ ...saleForm, harvest_id: e.target.value })} required>{availableHarvests.map((h) => <option key={h.id} value={h.id}>{h.bed} · {h.crop} · {h.available_kg} kg na voljo</option>)}</select></label>
        <label>Količina (kg)<input type="number" min="0.01" step="0.01" value={saleForm.quantity_kg} onChange={(e) => setSaleForm({ ...saleForm, quantity_kg: e.target.value })} required /></label>
        <label>Cena/kg (€)<input type="number" min="0.01" step="0.01" value={saleForm.price_per_kg_eur} onChange={(e) => setSaleForm({ ...saleForm, price_per_kg_eur: e.target.value })} required /></label>
        <label>Kupec<input value={saleForm.customer} onChange={(e) => setSaleForm({ ...saleForm, customer: e.target.value })} /></label>
        <button className="primary-button">SHRANI PRODAJO</button>
      </form>
    </section>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Rezultat na površino</p><h2>Dobiček po gredicah</h2></div></div><div className="economics-table"><strong>Gredica</strong><strong>Žetev</strong><strong>Stroški</strong><strong>Prihodki</strong><strong>Dobiček</strong>{economics.map((item) => <React.Fragment key={item.bed_id}><span>{item.bed}</span><span>{item.harvested_kg} kg</span><span>{item.costs_eur.toFixed(2)} €</span><span>{item.revenue_eur.toFixed(2)} €</span><strong className={item.profit_eur >= 0 ? "positive" : "negative"}>{item.profit_eur.toFixed(2)} €</strong></React.Fragment>)}</div></section>
  </>;
}

function OrdersView({ inventory, customers, orders, customerForm, setCustomerForm, createCustomer, orderForm, setOrderForm, createOrder, changeOrderStatus, openOrderDocument, document, setDocument, retailSales, quickSaleForm, setQuickSaleForm, createQuickSale, openRetailDocument, salesSettings, setSalesSettings, saveSalesSettings }) {
  const available = inventory.filter((item) => item.available_kg > 0);
  return <>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Prodajna zaloga</p><h2>Na voljo</h2></div><span>{available.reduce((sum, item) => sum + item.available_kg, 0).toFixed(1)} kg</span></div>
      <div className="inventory-grid">{inventory.map((item) => <article key={item.harvest_id}><strong>{item.crop} {item.variety}</strong><span>Gredica {item.bed} · kakovost {item.quality}</span><div><b>{item.available_kg} kg na voljo</b><small>{item.reserved_kg} kg rezervirano · {item.sold_kg} kg prodano</small></div></article>)}</div>
    </section>
    <section className="quick-sale-grid">
      <form className="panel quick-sale-form" onSubmit={createQuickSale}><div><p className="eyebrow">Tržnica in prodaja na domu</p><h2>Hitra prodaja</h2><span className="exemption-note">Končni potrošnik je privzet · račun ni predviden ob vključeni izjemi 81.a</span></div>
        <label>Kupec<select value={quickSaleForm.customer_id} onChange={(e) => setQuickSaleForm({ ...quickSaleForm, customer_id: e.target.value })}><option value="">Končni potrošnik (brez osebnih podatkov)</option>{customers.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.customer_type === "business" ? "poslovni" : "končni"}</option>)}</select></label>
        <label>Artikel<select value={quickSaleForm.harvest_id} onChange={(e) => setQuickSaleForm({ ...quickSaleForm, harvest_id: e.target.value })} required>{available.map((item) => <option key={item.harvest_id} value={item.harvest_id}>{item.crop} {item.variety} · {item.available_kg} kg</option>)}</select></label>
        <label>Količina (kg)<input type="number" min="0.01" step="0.01" value={quickSaleForm.quantity_kg} onChange={(e) => setQuickSaleForm({ ...quickSaleForm, quantity_kg: e.target.value })} required /></label>
        <label>Cena/kg (€)<input type="number" min="0.01" step="0.01" value={quickSaleForm.price_per_kg_eur} onChange={(e) => setQuickSaleForm({ ...quickSaleForm, price_per_kg_eur: e.target.value })} required /></label>
        <label>Plačilo<select value={quickSaleForm.payment_method} onChange={(e) => setQuickSaleForm({ ...quickSaleForm, payment_method: e.target.value })}><option value="cash">Gotovina</option><option value="card">Kartica</option><option value="bank_transfer">Nakazilo</option></select></label>
        <button className="primary-button">ZABELEŽI PRODAJO</button>
      </form>
      {salesSettings && <form className="panel compact-form" onSubmit={saveSalesSettings}><h2>Nastavitve prodaje</h2><label className="check-label"><input type="checkbox" checked={salesSettings.basic_agriculture_invoice_exemption} onChange={(e) => setSalesSettings({ ...salesSettings, basic_agriculture_invoice_exemption: e.target.checked })} /> Izjema osnovne kmetijske dejavnosti po 81.a</label><label>Naziv kmetije<input value={salesSettings.seller_name} onChange={(e) => setSalesSettings({ ...salesSettings, seller_name: e.target.value })} required /></label><label>Davčna številka<input value={salesSettings.seller_tax_number || ""} onChange={(e) => setSalesSettings({ ...salesSettings, seller_tax_number: e.target.value || null })} /></label><button className="secondary-button">SHRANI NASTAVITVE</button></form>}
    </section>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Neposredna prodaja</p><h2>Zadnje hitre prodaje</h2></div><span>{retailSales.length} zapisov</span></div><div className="retail-sales-list">{retailSales.map((sale) => <article key={sale.id}><div><strong>{sale.number} · {sale.customer}</strong><span>{sale.sale_date} · {sale.total_eur.toFixed(2)} € · {sale.payment_method === "cash" ? "gotovina" : sale.payment_method === "card" ? "kartica" : "nakazilo"}</span></div><div className="order-actions"><button className="text-button" onClick={() => openRetailDocument(sale.id, "receipt")}>POTRDILO</button>{sale.invoice_required && <button className="secondary-button" onClick={() => openRetailDocument(sale.id, "invoice")}>RAČUN</button>}</div></article>)}</div></section>
    <section className="order-entry-grid">
      <form className="panel compact-form" onSubmit={createCustomer}><h2>Nov kupec</h2>
        <label>Vrsta<select value={customerForm.customer_type} onChange={(e) => setCustomerForm({ ...customerForm, customer_type: e.target.value })}><option value="consumer">Končni potrošnik</option><option value="business">Poslovni kupec</option></select></label>
        <label>Naziv<input value={customerForm.name} onChange={(e) => setCustomerForm({ ...customerForm, name: e.target.value })} required /></label>
        <label>E-pošta<input type="email" value={customerForm.email} onChange={(e) => setCustomerForm({ ...customerForm, email: e.target.value })} /></label>
        <label>Telefon<input value={customerForm.phone} onChange={(e) => setCustomerForm({ ...customerForm, phone: e.target.value })} /></label>
        <label>Naslov<input value={customerForm.address} onChange={(e) => setCustomerForm({ ...customerForm, address: e.target.value })} /></label>
        {customerForm.customer_type === "business" && <label>Davčna številka<input value={customerForm.tax_number} onChange={(e) => setCustomerForm({ ...customerForm, tax_number: e.target.value })} required /></label>}
        <button className="primary-button">DODAJ KUPCA</button>
      </form>
      <form className="panel order-form" onSubmit={createOrder}><h2>Novo naročilo</h2>
        <label>Kupec<select value={orderForm.customer_id} onChange={(e) => setOrderForm({ ...orderForm, customer_id: e.target.value })} required>{customers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Artikel<select value={orderForm.harvest_id} onChange={(e) => setOrderForm({ ...orderForm, harvest_id: e.target.value })} required>{available.map((item) => <option key={item.harvest_id} value={item.harvest_id}>{item.crop} {item.variety} · {item.bed} · {item.available_kg} kg</option>)}</select></label>
        <label>Količina (kg)<input type="number" min="0.01" step="0.01" value={orderForm.quantity_kg} onChange={(e) => setOrderForm({ ...orderForm, quantity_kg: e.target.value })} required /></label>
        <label>Cena/kg (€)<input type="number" min="0.01" step="0.01" value={orderForm.price_per_kg_eur} onChange={(e) => setOrderForm({ ...orderForm, price_per_kg_eur: e.target.value })} required /></label>
        <label>Datum naročila<input type="date" value={orderForm.order_date} onChange={(e) => setOrderForm({ ...orderForm, order_date: e.target.value })} required /></label>
        <label>Dostava<input type="date" value={orderForm.delivery_date} onChange={(e) => setOrderForm({ ...orderForm, delivery_date: e.target.value })} required /></label>
        <button className="primary-button">POTRDI IN REZERVIRAJ</button>
      </form>
    </section>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Prodajni tok</p><h2>Naročila</h2></div><span>{orders.length} skupaj</span></div>
      <div className="orders-list">{orders.map((order) => <article key={order.id}><div className="order-head"><div><strong>{order.number} · {order.customer}</strong><span>Dostava {order.delivery_date} · {order.total_eur.toFixed(2)} €</span></div><span className={`order-status ${order.status}`}>{order.status === "confirmed" ? "Potrjeno" : order.status === "fulfilled" ? "Dostavljeno" : "Preklicano"}</span></div>
        <div className="order-lines">{order.items.map((item) => <span key={item.id}>{item.crop} {item.variety} · {item.quantity_kg} kg × {item.price_per_kg_eur.toFixed(2)} €</span>)}</div>
        <div className="order-actions"><button className="text-button" onClick={() => openOrderDocument(order.id, "delivery_note")}>DOBAVNICA</button>{order.status === "fulfilled" && order.customer_type === "business" && <button className="text-button" onClick={() => openOrderDocument(order.id, "invoice")}>RAČUN</button>}{order.status === "confirmed" && <><button className="secondary-button" onClick={() => changeOrderStatus(order.id, "fulfilled")}>DOSTAVLJENO</button><button className="text-button danger-text" onClick={() => changeOrderStatus(order.id, "cancelled")}>PREKLIČI</button></>}</div>
      </article>)}</div>
    </section>
    {document && (() => { const record = document.order || document.sale; const customer = document.customer || { name: record.customer, address: "" }; return <section className="panel printable-document"><div className="section-heading"><div><p className="eyebrow">{document.document_type === "invoice" ? "Račun" : document.document_type === "delivery_note" ? "Dobavnica" : "Interno potrdilo prodaje"}</p><h2>{document.document_number}</h2></div><div className="order-actions"><button className="secondary-button" onClick={() => window.print()}>NATISNI</button><button className="icon-button" onClick={() => setDocument(null)}>✕</button></div></div>{document.seller && <p><strong>{document.seller.name}</strong><br />{document.seller.tax_number || ""}</p>}<p><strong>Kupec:</strong> {customer.name}<br />{customer.address || ""}</p><div className="document-lines">{record.items.map((item) => <div key={item.id}><span>{item.crop} {item.variety} · {item.quantity_kg} kg</span><strong>{item.line_total_eur.toFixed(2)} €</strong></div>)}</div><div className="document-total">Skupaj <strong>{record.total_eur.toFixed(2)} €</strong></div>{document.fiscal_confirmation_required && <p className="forecast-warning">Ta račun je treba pred uporabo vključiti v ustrezen postopek davčnega potrjevanja.</p>}</section>; })()}
  </>;
}

function SalesReportView({ report, start, setStart, end, setEnd }) {
  const summary = report.summary || {};
  const paymentLabel = (method) => ({ cash: "Gotovina", card: "Kartica", bank_transfer: "Nakazilo", invoice: "Izdani račun", unclassified: "Ni določeno" }[method] || method);
  return <>
    <section className="panel report-heading">
      <div><p className="eyebrow">Dnevni register</p><h2>Pregled prodaje</h2><p className="muted">{report.note}</p></div>
      <div className="report-controls"><label>Od<input type="date" value={start} onChange={(e) => { const value = e.target.value; setStart(value); if (end < value) setEnd(value); }} /></label><label>Do<input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} /></label><a className="secondary-button export-button" href={`${API_URL}/api/sales-report/export.csv?start=${start}&end=${end}`}>IZVOZI CSV</a></div>
    </section>
    <section className="metric-grid report-metrics">
      <article className="metric-card"><span>Skupaj</span><strong>{(summary.total_eur || 0).toFixed(2)} €</strong><small>{summary.transactions || 0} prodaj · nerazvrščeno {(summary.unclassified_eur || 0).toFixed(2)} €</small></article>
      <article className="metric-card"><span>Gotovina</span><strong>{(summary.cash_eur || 0).toFixed(2)} €</strong><small>prejeto ob prodaji</small></article>
      <article className="metric-card"><span>Kartice</span><strong>{(summary.card_eur || 0).toFixed(2)} €</strong><small>kartična plačila</small></article>
      <article className="metric-card"><span>Nakazila</span><strong>{(summary.bank_transfer_eur || 0).toFixed(2)} €</strong><small>evidentirana plačila</small></article>
      <article className="metric-card"><span>Izdani računi</span><strong>{(summary.invoice_eur || 0).toFixed(2)} €</strong><small>{summary.invoice_count || 0} računov · ne pomeni plačano</small></article>
      <article className="metric-card"><span>Poslovni kupci</span><strong>{(summary.business_eur || 0).toFixed(2)} €</strong><small>končni kupci {(summary.consumer_eur || 0).toFixed(2)} €</small></article>
    </section>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Po dnevih</p><h2>Dnevni seštevki</h2></div><span>{report.daily.length} dni</span></div>
      {report.daily.length === 0 ? <p className="empty-state">V izbranem obdobju še ni evidentirane prodaje.</p> : <div className="daily-sales-list">{report.daily.map((day) => <article key={day.date}><div><time>{day.date}</time><strong>{day.total_eur.toFixed(2)} €</strong><span>{day.transactions} prodaj</span></div><small>Gotovina {day.cash_eur.toFixed(2)} € · kartice {day.card_eur.toFixed(2)} € · nakazila {day.bank_transfer_eur.toFixed(2)} € · računi {day.invoice_eur.toFixed(2)} €</small></article>)}</div>}
    </section>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Knjiga prodaje</p><h2>Posamezni zapisi</h2></div><span>{report.entries.length} zapisov</span></div>
      <div className="sales-report-table"><b>Datum</b><b>Dokument</b><b>Kupec</b><b>Način</b><b>Znesek</b>{report.entries.map((entry) => <React.Fragment key={entry.key}><span>{entry.date}</span><span>{entry.number}<small>{entry.source === "order" ? "naročilo" : "hitra prodaja"}</small></span><span>{entry.customer}<small>{entry.customer_type === "business" ? "poslovni" : "končni"}</small></span><span>{paymentLabel(entry.payment_method)}{entry.invoice_required && <small>račun</small>}</span><strong>{entry.total_eur.toFixed(2)} €</strong></React.Fragment>)}</div>
    </section>
  </>;
}

function ReceivablesView({ data, asOf, setAsOf, includePaid, setIncludePaid, paymentOrderId, beginPayment, cancelPayment, paymentForm, setPaymentForm, recordPayment }) {
  const summary = data.summary || {};
  const statusLabel = (value) => ({ open: "Odprto", partial: "Delno plačano", overdue: "Zapadlo", paid: "Plačano" }[value] || value);
  const methodLabel = (value) => ({ cash: "gotovina", card: "kartica", bank_transfer: "nakazilo" }[value] || value);
  return <>
    <section className="panel receivables-heading"><div><p className="eyebrow">Poslovni računi</p><h2>Terjatve in plačila</h2><p className="muted">{data.note}</p></div><div className="receivable-filters"><label>Stanje na dan<input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></label><label className="check-label"><input type="checkbox" checked={includePaid} onChange={(e) => setIncludePaid(e.target.checked)} /> Prikaži tudi plačane</label></div></section>
    <section className="metric-grid receivable-metrics">
      <article className="metric-card"><span>Odprto</span><strong>{(summary.outstanding_eur || 0).toFixed(2)} €</strong><small>{summary.open_count || 0} računov</small></article>
      <article className="metric-card"><span>Zapadlo</span><strong>{(summary.overdue_eur || 0).toFixed(2)} €</strong><small>{summary.overdue_count || 0} računov</small></article>
      <article className="metric-card"><span>Prejeto</span><strong>{(summary.paid_eur || 0).toFixed(2)} €</strong><small>od {(summary.invoiced_eur || 0).toFixed(2)} € izdanih</small></article>
    </section>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Pregled računov</p><h2>Odprte postavke</h2></div><span>{data.items.length} zapisov</span></div>
      {data.items.length === 0 ? <p className="empty-state">Ni odprtih terjatev.</p> : <div className="receivables-list">{data.items.map((item) => <article key={item.order_id} className={item.status}><div className="receivable-main"><div><span className={`receivable-state ${item.status}`}>{statusLabel(item.status)}</span><strong>{item.invoice_number} · {item.customer}</strong><span>Rok {item.due_date}{item.days_overdue > 0 ? ` · ${item.days_overdue} dni zamude` : ""}</span></div><div><strong>{item.outstanding_eur.toFixed(2)} € odprto</strong><span>{item.paid_eur.toFixed(2)} € od {item.total_eur.toFixed(2)} € plačano</span></div></div>{item.payments.length > 0 && <div className="payment-history">{item.payments.map((payment) => <span key={payment.id}>{payment.payment_date} · {payment.amount_eur.toFixed(2)} € · {methodLabel(payment.payment_method)}</span>)}</div>}{item.status !== "paid" && paymentOrderId !== item.order_id && <button className="secondary-button" onClick={() => beginPayment(item)}>EVIDENTIRAJ PLAČILO</button>}{paymentOrderId === item.order_id && <form className="payment-form" onSubmit={recordPayment}><label>Datum<input type="date" value={paymentForm.payment_date} onChange={(e) => setPaymentForm({ ...paymentForm, payment_date: e.target.value })} required /></label><label>Znesek (€)<input type="number" min="0.01" max={item.outstanding_eur} step="0.01" value={paymentForm.amount_eur} onChange={(e) => setPaymentForm({ ...paymentForm, amount_eur: e.target.value })} required /></label><label>Način<select value={paymentForm.payment_method} onChange={(e) => setPaymentForm({ ...paymentForm, payment_method: e.target.value })}><option value="bank_transfer">Nakazilo</option><option value="cash">Gotovina</option><option value="card">Kartica</option></select></label><label>Opomba<input value={paymentForm.notes} onChange={(e) => setPaymentForm({ ...paymentForm, notes: e.target.value })} /></label><div className="payment-actions"><button type="button" className="text-button" onClick={cancelPayment}>PREKLIČI</button><button className="primary-button">SHRANI PLAČILO</button></div></form>}</article>)}</div>}
    </section>
  </>;
}

function PlanningView({ crops, beds, plans, calendar, forecast, form, setForm, selectedCrop, changeCrop, createPlan, activatePlan, cancelPlan, start, setStart, end, setEnd }) {
  return <>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Sezonski načrt</p><h2>Načrtuj setev ali serijo</h2></div></div>
      <form className="planning-form" onSubmit={createPlan}>
        <label>Gredica<select value={form.bed_id} onChange={(e) => setForm({ ...form, bed_id: e.target.value })} required>{beds.map((bed) => <option key={bed.id} value={bed.id}>{bed.name} · {bed.area_m2} m²</option>)}</select></label>
        <label>Kultura<select value={form.crop_id} onChange={changeCrop} required>{crops.map((crop) => <option key={crop.id} value={crop.id}>{crop.name}</option>)}</select></label>
        <label>Sorta<select value={form.variety_id} onChange={(e) => setForm({ ...form, variety_id: e.target.value })} required>{(selectedCrop?.varieties || []).map((item) => <option key={item.id} value={item.id}>{item.name} · {item.days_to_harvest} dni</option>)}</select></label>
        <label>Setev<input type="date" value={form.sowing_date} onChange={(e) => setForm({ ...form, sowing_date: e.target.value })} required /></label>
        <label>Presajanje<input type="date" value={form.transplant_date} onChange={(e) => setForm({ ...form, transplant_date: e.target.value })} /></label>
        <label>Pričakovano (kg)<input type="number" min="0.1" step="0.1" value={form.expected_yield_kg} onChange={(e) => setForm({ ...form, expected_yield_kg: e.target.value })} required /></label>
        <label>Število setev<input type="number" min="1" max="20" value={form.succession_count} onChange={(e) => setForm({ ...form, succession_count: e.target.value })} required /></label>
        <label>Razmik (dni)<input type="number" min="1" value={form.succession_interval_days} onChange={(e) => setForm({ ...form, succession_interval_days: e.target.value })} required /></label>
        <button className="primary-button">DODAJ V NAČRT</button>
      </form>
    </section>
    <section className="planning-summary-grid">
      <div className="panel"><div className="section-heading"><div><p className="eyebrow">Obdobje</p><h2>Koledar dela</h2></div></div><div className="range-form"><label>Od<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label><label>Do<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label></div><div className="calendar-list">{calendar.map((event, index) => <article key={`${event.date}-${event.type}-${index}`}><time>{event.date}</time><div><strong>{event.title}</strong><span>{event.bed ? `Gredica ${event.bed}` : event.type === "delivery" ? "Prodaja" : "Splošno"}</span></div><span className={`event-type ${event.type}`}>{event.type === "sowing" ? "Setev" : event.type === "transplant" ? "Presajanje" : event.type === "planned_harvest" ? "Žetev" : event.type === "delivery" ? "Dostava" : "Opravilo"}</span></article>)}</div></div>
      <div className="panel"><div className="section-heading"><div><p className="eyebrow">Ponudba in povpraševanje</p><h2>Napoved pridelka</h2></div></div>{forecast.warnings.map((warning) => <div className="forecast-warning" key={warning}>⚠ {warning}</div>)}<div className="forecast-list">{forecast.rows.map((row) => <article key={row.crop_id}><div><strong>{row.crop}</strong><span>Zaloga {row.current_stock_kg} kg + načrt {row.planned_yield_kg} kg − naročila {row.confirmed_demand_kg} kg</span></div><b className={row.shortage ? "negative" : "positive"}>{row.projected_balance_kg} kg</b></article>)}</div></div>
    </section>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Prihodnje setve</p><h2>Načrtovane gredice</h2></div><span>{plans.length} zapisov</span></div><div className="plan-grid">{plans.map((plan) => <article key={plan.id}><div><span className={`plan-state ${plan.status}`}>{plan.status === "planned" ? "Načrtovano" : "Aktivirano"}</span><strong>{plan.crop} {plan.variety}</strong><span>Gredica {plan.bed} · setev {plan.sowing_date}</span><span>Žetev {plan.expected_harvest_date} · {plan.expected_yield_kg} kg</span></div>{plan.status === "planned" && <div className="order-actions"><button className="secondary-button" onClick={() => activatePlan(plan.id)}>AKTIVIRAJ</button><button className="text-button danger-text" onClick={() => cancelPlan(plan.id)}>PREKLIČI</button></div>}</article>)}</div></section>
  </>;
}

createRoot(document.getElementById("root")).render(<React.StrictMode><App /></React.StrictMode>);
