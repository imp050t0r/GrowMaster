import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { GREDICNIK_MODES, getGredicnikSpacing, getGredicnikSpacingOptions } from "./gredicnikSpacing";
import { formatPlantingMonths, PLANTING_ENVIRONMENTS, plantingTiming, toleranceLabel } from "./plantingCalendar";
import {
  apiFetch,
  apiRequest,
  configuredServerUrl,
  forgetServer,
  isNativeApp,
  registerGrowMasterServiceWorker,
  saveNativeSession,
  saveServerUrl,
  testServerConnection,
} from "./platform";

const now = new Date();
const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
const monthStart = `${today.slice(0, 7)}-01`;
const yearStart = `${today.slice(0, 4)}-01-01`;
const inDays = (days) => {
  const value = new Date(now); value.setDate(value.getDate() + days);
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
};

const maturitySeasonForDate = (dateValue) => {
  const month = Number(String(dateValue || "").slice(5, 7));
  if ([3, 4, 5].includes(month)) return { key: "spring", label: "pomlad" };
  if ([6, 7, 8].includes(month)) return { key: "summer", label: "poletje" };
  if ([9, 10, 11].includes(month)) return { key: "autumn", label: "jesen" };
  return { key: "winter", label: "zima" };
};
const maturityDaysForDate = (variety, dateValue) => {
  const season = maturitySeasonForDate(dateValue);
  return variety?.[`days_${season.key}`] ?? variety?.days_to_harvest ?? "—";
};

async function downloadProtectedFile(path, filename, openInNewWindow = false) {
  const previewWindow = openInNewWindow ? window.open("", "_blank") : null;
  const response = await apiFetch(path);
  if (!response.ok) {
    previewWindow?.close();
    throw new Error("Datoteke ni mogoče prenesti.");
  }
  const objectUrl = URL.createObjectURL(await response.blob());
  if (previewWindow) {
    previewWindow.opener = null;
    previewWindow.location = objectUrl;
  } else {
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    link.click();
  }
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

function ProtectedDownloadButton({ path, filename, children, className = "secondary-button", open = false }) {
  return <button type="button" className={className} onClick={() => downloadProtectedFile(path, filename, open).catch((error) => window.alert(error.message))}>{children}</button>;
}

const taskTypeLabels = {
  general: "Splošno",
  inspection: "Pregled",
  irrigation: "Namakanje",
  bed_preparation: "Priprava gredice",
  emergence_check: "Pregled vznika",
  growth_check: "Pregled rasti",
  harvest_check: "Kontrola žetve",
  harvest_followup: "Pregled žetve",
  bed_planning: "Načrt zasaditve",
};

function App() {
  const [serverReady, setServerReady] = useState(!isNativeApp || Boolean(configuredServerUrl()));
  const [online, setOnline] = useState(navigator.onLine);
  const [installPrompt, setInstallPrompt] = useState(null);
  const [auth, setAuth] = useState({ loading: true, configured: false, authenticated: false, display_name: null, session_days: 30, demo_data_available: false });
  const [authForm, setAuthForm] = useState({ display_name: "", farm_name: "", keep_demo_data: false, password: "", confirmation: "" });
  const [view, setView] = useState("dashboard");
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const [crops, setCrops] = useState([]);
  const [beds, setBeds] = useState([]);
  const [plantings, setPlantings] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [taskReview, setTaskReview] = useState(null);
  const [selectedReviewKeys, setSelectedReviewKeys] = useState([]);
  const [reviewApplying, setReviewApplying] = useState(false);
  const [harvests, setHarvests] = useState([]);
  const [economics, setEconomics] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [priceList, setPriceList] = useState([]);
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
  const [cashFlow, setCashFlow] = useState({ summary: {}, daily: [], entries: [], note: "" });
  const [dayCloses, setDayCloses] = useState([]);
  const [dayClosePreview, setDayClosePreview] = useState(null);
  const [suppliers, setSuppliers] = useState([]);
  const [supplyItems, setSupplyItems] = useState([]);
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [supplyUsages, setSupplyUsages] = useState([]);
  const [workers, setWorkers] = useState([]);
  const [laborReport, setLaborReport] = useState({ summary: {}, by_worker: [], by_bed: [], entries: [], note: "" });
  const [profitabilityReport, setProfitabilityReport] = useState({ summary: {}, by_bed: [], by_crop: [], note: "" });
  const [farmExpenses, setFarmExpenses] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [invoiceProfile, setInvoiceProfile] = useState(null);
  const [dataSafety, setDataSafety] = useState({ daily_backups: [], automatic_backups: [] });
  const [readiness, setReadiness] = useState({ operational_ready: false, business_documents_ready: false, checks: [] });
  const [account, setAccount] = useState({ display_name: "", active_sessions: 0, session_days: 30 });
  const [farmProfile, setFarmProfile] = useState({ farm_name: "", basic_agriculture_invoice_exemption: true, seller_tax_number: null, seller_address: "", seller_iban: null, seller_registration_number: null, vat_note: null, business_premise_code: "GM", device_code: "01", default_due_days: 14, business_documents_ready: false });
  const [reportStart, setReportStart] = useState(today);
  const [reportEnd, setReportEnd] = useState(today);
  const [receivablesAsOf, setReceivablesAsOf] = useState(today);
  const [includePaidReceivables, setIncludePaidReceivables] = useState(false);
  const [cashFlowStart, setCashFlowStart] = useState(monthStart);
  const [cashFlowEnd, setCashFlowEnd] = useState(today);
  const [laborStart, setLaborStart] = useState(monthStart);
  const [laborEnd, setLaborEnd] = useState(today);
  const [profitabilityStart, setProfitabilityStart] = useState(yearStart);
  const [profitabilityEnd, setProfitabilityEnd] = useState(today);
  const [paymentOrderId, setPaymentOrderId] = useState(null);
  const [planStart, setPlanStart] = useState(today);
  const [planEnd, setPlanEnd] = useState(inDays(90));
  const [taskDate, setTaskDate] = useState(today);
  const [selectedBed, setSelectedBed] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [rotationWarning, setRotationWarning] = useState(null);
  const [plantingSuggestions, setPlantingSuggestions] = useState(null);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [completionTaskId, setCompletionTaskId] = useState(null);

  const [plantingForm, setPlantingForm] = useState({
    crop_id: "",
    variety_id: "",
    bed_id: "",
    sowing_date: today,
  });
  const [bedForm, setBedForm] = useState({ name: "", width_m: "0.8", length_m: "15" });
  const [bedSizeForm, setBedSizeForm] = useState({ width_m: "", length_m: "" });
  const [cropForm, setCropForm] = useState({ name: "", family: "", category: "" });
  const [varietyForm, setVarietyForm] = useState({ crop_id: "", name: "", days_spring: "", days_summer: "", days_autumn: "", days_winter: "", composition: "" });
  const [taskForm, setTaskForm] = useState({
    title: "",
    task_type: "general",
    due_date: today,
    bed_id: "",
    priority: "normal",
  });
  const [completion, setCompletion] = useState({
    duration_minutes: "",
    worker_id: "",
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
  const [quickSaleCart, setQuickSaleCart] = useState([]);
  const [priceForm, setPriceForm] = useState({ crop_id: "", quality: "A", price_per_kg_eur: "" });
  const [paymentForm, setPaymentForm] = useState({ payment_date: today, amount_eur: "", payment_method: "bank_transfer", notes: "" });
  const [dayCloseForm, setDayCloseForm] = useState({ business_date: today, opening_cash_eur: "0", counted_cash_eur: "", notes: "" });
  const [supplierForm, setSupplierForm] = useState({ name: "", tax_number: "", email: "", phone: "" });
  const [supplyItemForm, setSupplyItemForm] = useState({ name: "", category: "seed", unit: "kos", opening_stock: "0", reorder_level: "0" });
  const [purchaseForm, setPurchaseForm] = useState({ supplier_id: "", supply_item_id: "", order_date: today, expected_date: "", payment_method: "bank_transfer", quantity: "", unit_price_eur: "", notes: "" });
  const [purchaseCart, setPurchaseCart] = useState([]);
  const [supplyUsageForm, setSupplyUsageForm] = useState({ supply_item_id: "", bed_id: "", planting_id: "", usage_date: today, quantity: "", unit_cost_eur: "", notes: "" });
  const [supplierPaymentOrderId, setSupplierPaymentOrderId] = useState(null);
  const [supplierPaymentForm, setSupplierPaymentForm] = useState({ payment_date: today, amount_eur: "", payment_method: "bank_transfer", notes: "" });
  const [workerForm, setWorkerForm] = useState({ name: "", role: "", hourly_rate_eur: "" });
  const [laborForm, setLaborForm] = useState({ worker_id: "", bed_id: "", planting_id: "", work_date: today, duration_minutes: "", hourly_rate_eur: "", description: "" });
  const [farmExpenseForm, setFarmExpenseForm] = useState({ expense_date: today, category: "fuel", amount_eur: "", payment_method: "cash", supplier: "", reference: "", description: "" });
  const [restoreFile, setRestoreFile] = useState(null);
  const [restoreConfirmation, setRestoreConfirmation] = useState("");
  const [accountForm, setAccountForm] = useState({ display_name: "", current_password: "" });
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "", confirmation: "" });

  const selectedCrop = useMemo(
    () => crops.find((crop) => String(crop.id) === String(plantingForm.crop_id)),
    [crops, plantingForm.crop_id],
  );
  const selectedPlanCrop = useMemo(
    () => crops.find((crop) => String(crop.id) === String(planForm.crop_id)),
    [crops, planForm.crop_id],
  );

  async function loadData() {
    const [cropData, bedData, plantingData, taskData, dashboardData, taskReviewData, harvestData, economicsData, inventoryData, priceData, customerData, orderData, planData, calendarData, forecastData, retailSaleData, salesSettingsData, salesReportData, receivablesData, cashFlowData, dayCloseData, supplierData, supplyItemData, purchaseOrderData, supplyUsageData, workerData, laborData, profitabilityData, farmExpenseData, invoiceData, invoiceProfileData, farmProfileData] = await Promise.all([
      apiRequest("/api/crops"),
      apiRequest("/api/beds"),
      apiRequest("/api/plantings"),
      apiRequest(`/api/tasks?date=${taskDate}`),
      apiRequest(`/api/dashboard?date=${today}`),
      apiRequest(`/api/task-review?date=${today}&horizon_days=7`),
      apiRequest("/api/harvests"),
      apiRequest("/api/economics/by-bed"),
      apiRequest("/api/inventory"),
      apiRequest("/api/price-list"),
      apiRequest("/api/customers"),
      apiRequest("/api/orders"),
      apiRequest("/api/plans"),
      apiRequest(`/api/planning/calendar?start=${planStart}&end=${planEnd}`),
      apiRequest(`/api/planning/forecast?start=${planStart}&end=${planEnd}`),
      apiRequest("/api/retail-sales"),
      apiRequest("/api/sales-settings"),
      apiRequest(`/api/sales-report?start=${reportStart}&end=${reportEnd}`),
      apiRequest(`/api/receivables?as_of=${receivablesAsOf}&include_paid=${includePaidReceivables}`),
      apiRequest(`/api/cash-flow?start=${cashFlowStart}&end=${cashFlowEnd}`),
      apiRequest("/api/day-closes"),
      apiRequest("/api/suppliers"),
      apiRequest("/api/supply-items"),
      apiRequest("/api/purchase-orders"),
      apiRequest("/api/supply-usages"),
      apiRequest("/api/workers"),
      apiRequest(`/api/labor-report?start=${laborStart}&end=${laborEnd}`),
      apiRequest(`/api/profitability-report?start=${profitabilityStart}&end=${profitabilityEnd}`),
      apiRequest(`/api/farm-expenses?start=${profitabilityStart}&end=${profitabilityEnd}`),
      apiRequest("/api/invoices"),
      apiRequest("/api/invoice-profile"),
      apiRequest("/api/farm-profile"),
    ]);
    setCrops(cropData);
    setBeds(bedData);
    setPlantings(plantingData);
    setTasks(taskData);
    setDashboard(dashboardData);
    setTaskReview(taskReviewData);
    setSelectedReviewKeys(taskReviewData.suggestions.map((suggestion) => suggestion.key));
    setHarvests(harvestData);
    setEconomics(economicsData);
    setInventory(inventoryData);
    setPriceList(priceData);
    setCustomers(customerData);
    setOrders(orderData);
    setPlans(planData);
    setPlanningCalendar(calendarData.events);
    setForecast(forecastData);
    setRetailSales(retailSaleData);
    setSalesSettings(salesSettingsData);
    setSalesReport(salesReportData);
    setReceivables(receivablesData);
    setCashFlow(cashFlowData);
    setDayCloses(dayCloseData);
    setSuppliers(supplierData);
    setSupplyItems(supplyItemData);
    setPurchaseOrders(purchaseOrderData);
    setSupplyUsages(supplyUsageData);
    setWorkers(workerData);
    setLaborReport(laborData);
    setProfitabilityReport(profitabilityData);
    setFarmExpenses(farmExpenseData);
    setInvoices(invoiceData);
    setInvoiceProfile(invoiceProfileData);
    setFarmProfile(farmProfileData);
    setHarvestForm((current) => ({ ...current, planting_id: current.planting_id || plantingData[0]?.id || "" }));
    setCostForm((current) => ({ ...current, bed_id: current.bed_id || bedData[0]?.id || "" }));
    setSaleForm((current) => ({ ...current, harvest_id: current.harvest_id || harvestData.find((item) => item.available_kg > 0)?.id || "" }));
    setOrderForm((current) => ({
      ...current,
      customer_id: current.customer_id || customerData[0]?.id || "",
      harvest_id: current.harvest_id || inventoryData.find((item) => item.available_kg > 0)?.harvest_id || "",
    }));
    setQuickSaleForm((current) => {
      const selected = inventoryData.find((item) => String(item.harvest_id) === String(current.harvest_id) && item.available_kg > 0) || inventoryData.find((item) => item.available_kg > 0);
      const sameSelection = String(selected?.harvest_id || "") === String(current.harvest_id || "");
      return { ...current, harvest_id: selected?.harvest_id || "", price_per_kg_eur: sameSelection && current.price_per_kg_eur ? current.price_per_kg_eur : selected?.suggested_price_per_kg_eur || "" };
    });
    setPriceForm((current) => ({ ...current, crop_id: current.crop_id || cropData[0]?.id || "" }));
    setVarietyForm((current) => ({ ...current, crop_id: current.crop_id || cropData[0]?.id || "" }));
    setPurchaseForm((current) => ({
      ...current,
      supplier_id: current.supplier_id || supplierData[0]?.id || "",
      supply_item_id: current.supply_item_id || supplyItemData[0]?.id || "",
    }));
    setSupplyUsageForm((current) => ({
      ...current,
      supply_item_id: current.supply_item_id || supplyItemData[0]?.id || "",
      bed_id: current.bed_id || bedData[0]?.id || "",
    }));
    setCompletion((current) => ({
      ...current,
      worker_id: current.worker_id || workerData.find((item) => item.active)?.id || "",
    }));
    setLaborForm((current) => ({
      ...current,
      worker_id: current.worker_id || workerData.find((item) => item.active)?.id || "",
      bed_id: current.bed_id || bedData[0]?.id || "",
    }));
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
    if (!serverReady) return;
    apiRequest("/api/auth/status")
      .then((status) => setAuth({ ...status, loading: false }))
      .catch((loadError) => { setAuth((current) => ({ ...current, loading: false })); setError(loadError.message); });
    const handleUnauthorized = () => setAuth((current) => ({ ...current, authenticated: false, display_name: null }));
    window.addEventListener("growmaster:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("growmaster:unauthorized", handleUnauthorized);
  }, [serverReady]);

  useEffect(() => {
    const updateOnlineState = () => setOnline(navigator.onLine);
    const captureInstallPrompt = (event) => {
      event.preventDefault();
      setInstallPrompt(event);
    };
    window.addEventListener("online", updateOnlineState);
    window.addEventListener("offline", updateOnlineState);
    window.addEventListener("beforeinstallprompt", captureInstallPrompt);
    return () => {
      window.removeEventListener("online", updateOnlineState);
      window.removeEventListener("offline", updateOnlineState);
      window.removeEventListener("beforeinstallprompt", captureInstallPrompt);
    };
  }, []);

  useEffect(() => {
    if (!auth.authenticated) return;
    loadData().catch((loadError) => setError(loadError.message));
  }, [auth.authenticated, taskDate, planStart, planEnd, reportStart, reportEnd, receivablesAsOf, includePaidReceivables, cashFlowStart, cashFlowEnd, laborStart, laborEnd, profitabilityStart, profitabilityEnd]);

  useEffect(() => {
    if (!auth.authenticated || view !== "data") return;
    Promise.all([
      apiRequest("/api/system/data-safety"),
      apiRequest("/api/system/readiness"),
    ])
      .then(([safetyData, readinessData]) => {
        setDataSafety(safetyData);
        setReadiness(readinessData);
      })
      .catch((loadError) => setError(loadError.message));
  }, [auth.authenticated, view]);

  useEffect(() => {
    if (!auth.authenticated || view !== "settings") return;
    apiRequest("/api/auth/account")
      .then((data) => {
        setAccount(data);
        setAccountForm((current) => ({ ...current, display_name: data.display_name }));
      })
      .catch((loadError) => setError(loadError.message));
  }, [auth.authenticated, view]);

  useEffect(() => {
    const openingCash = Number(dayCloseForm.opening_cash_eur);
    if (!auth.authenticated || !dayCloseForm.business_date || !Number.isFinite(openingCash) || openingCash < 0) return;
    apiRequest(`/api/day-closes/preview?business_date=${dayCloseForm.business_date}&opening_cash_eur=${openingCash}`)
      .then(setDayClosePreview)
      .catch((loadError) => setError(loadError.message));
  }, [auth.authenticated, dayCloseForm.business_date, dayCloseForm.opening_cash_eur]);

  async function submitAuthentication(event) {
    event.preventDefault(); clearMessages();
    if (!auth.configured && authForm.password !== authForm.confirmation) {
      setError("Vneseni gesli se ne ujemata."); return;
    }
    try {
      const setup = !auth.configured;
      const data = await apiRequest(setup ? "/api/auth/setup" : "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(setup ? { display_name: authForm.display_name, farm_name: authForm.farm_name, keep_demo_data: authForm.keep_demo_data, password: authForm.password } : { password: authForm.password }),
      });
      saveNativeSession(data.session_token);
      setAuth({ ...data, loading: false });
      setAuthForm({ display_name: "", farm_name: "", keep_demo_data: false, password: "", confirmation: "" });
      setNotice(data.message);
    } catch (requestError) { setError(requestError.message); }
  }

  async function logout() {
    clearMessages();
    try {
      await apiRequest("/api/auth/logout", { method: "POST" });
      saveNativeSession("");
      setAuth((current) => ({ ...current, authenticated: false, display_name: null }));
      setAuthForm({ display_name: "", farm_name: "", keep_demo_data: false, password: "", confirmation: "" });
    } catch (requestError) { setError(requestError.message); }
  }

  async function updateAccount(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/auth/account", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(accountForm),
      });
      setAccount(data);
      setAccountForm({ display_name: data.display_name, current_password: "" });
      setAuth((current) => ({ ...current, display_name: data.display_name }));
      setNotice(data.message);
    } catch (requestError) { setError(requestError.message); }
  }

  async function changePassword(event) {
    event.preventDefault(); clearMessages();
    if (passwordForm.new_password !== passwordForm.confirmation) {
      setError("Novi gesli se ne ujemata."); return;
    }
    try {
      const data = await apiRequest("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: passwordForm.current_password, new_password: passwordForm.new_password }),
      });
      saveNativeSession(data.session_token);
      setAccount(data);
      setPasswordForm({ current_password: "", new_password: "", confirmation: "" });
      setNotice(data.message);
    } catch (requestError) { setError(requestError.message); }
  }

  async function saveFarmProfile(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/farm-profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(farmProfile),
      });
      setFarmProfile(data);
      setSalesSettings((current) => ({ ...current, seller_name: data.farm_name, seller_tax_number: data.seller_tax_number, basic_agriculture_invoice_exemption: data.basic_agriculture_invoice_exemption }));
      setInvoiceProfile((current) => ({ ...current, seller_address: data.seller_address, seller_iban: data.seller_iban, seller_registration_number: data.seller_registration_number, vat_note: data.vat_note, business_premise_code: data.business_premise_code, device_code: data.device_code, default_due_days: data.default_due_days }));
      setNotice(data.message);
    } catch (requestError) { setError(requestError.message); }
  }

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
    setPlantingSuggestions(null);
  }

  async function requestPlantingSuggestions() {
    clearMessages();
    setSuggestionsLoading(true);
    try {
      const data = await apiRequest("/api/planting-suggestions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          crop_id: Number(plantingForm.crop_id),
          variety_id: Number(plantingForm.variety_id),
          sowing_date: plantingForm.sowing_date,
        }),
      });
      setPlantingSuggestions(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSuggestionsLoading(false);
    }
  }

  function applyPlantingSuggestion(suggestion) {
    setPlantingForm((current) => ({
      ...current,
      crop_id: suggestion.crop_id,
      variety_id: suggestion.variety_id,
      bed_id: suggestion.bed_id,
    }));
    setRotationWarning(null);
    setNotice(
      `Predlog je pripravljen: ${suggestion.crop} ${suggestion.variety} na gredici ${suggestion.bed}.`,
    );
  }

  async function savePlanting(overrideRotation = false) {
    clearMessages();
    const response = await apiFetch("/api/plantings", {
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
    setPlantingSuggestions(null);
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

  async function createCrop(event) {
    event.preventDefault();
    clearMessages();
    try {
      const data = await apiRequest("/api/crops", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cropForm),
      });
      setCropForm({ name: "", family: "", category: "" });
      setVarietyForm((current) => ({ ...current, crop_id: data.id }));
      setNotice(`${data.name} je dodan med zelenjavo. Zdaj lahko dodaš še sorte.`);
      await loadData();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function createVariety(event) {
    event.preventDefault();
    clearMessages();
    try {
      const data = await apiRequest(`/api/crops/${varietyForm.crop_id}/varieties`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: varietyForm.name,
          days_to_harvest: Number(varietyForm.days_spring),
          days_spring: Number(varietyForm.days_spring),
          days_summer: Number(varietyForm.days_summer),
          days_autumn: Number(varietyForm.days_autumn),
          days_winter: Number(varietyForm.days_winter),
          composition: varietyForm.composition || null,
        }),
      });
      setVarietyForm((current) => ({ ...current, name: "", days_spring: "", days_summer: "", days_autumn: "", days_winter: "", composition: "" }));
      setNotice(`Sorta ${data.name} je dodana.`);
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
      setBedSizeForm({ width_m: String(detail.width_m), length_m: String(detail.length_m) });
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function updateBedSize(event) {
    event.preventDefault();
    if (!selectedBed) return;
    clearMessages();
    try {
      const updated = await apiRequest(`/api/beds/${selectedBed.id}/size`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          width_m: Number(bedSizeForm.width_m),
          length_m: Number(bedSizeForm.length_m),
        }),
      });
      await loadData();
      const detail = await apiRequest(`/api/beds/${selectedBed.id}`);
      setSelectedBed(detail);
      setBedSizeForm({ width_m: String(detail.width_m), length_m: String(detail.length_m) });
      setNotice(updated.message);
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

  function toggleReviewSuggestion(key) {
    setSelectedReviewKeys((current) => (
      current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key]
    ));
  }

  function selectAllReviewSuggestions() {
    const allKeys = taskReview?.suggestions.map((suggestion) => suggestion.key) || [];
    setSelectedReviewKeys((current) => current.length === allKeys.length ? [] : allKeys);
  }

  async function applyTaskReview() {
    if (!selectedReviewKeys.length) return;
    clearMessages();
    setReviewApplying(true);
    try {
      const data = await apiRequest("/api/task-review/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          review_date: taskReview.review_date,
          horizon_days: taskReview.horizon_days,
          selected_keys: selectedReviewKeys,
        }),
      });
      setNotice(data.message);
      await loadData();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setReviewApplying(false);
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
          worker_id: completion.worker_id ? Number(completion.worker_id) : null,
          quantity_used: completion.quantity_used ? Number(completion.quantity_used) : null,
          unit: completion.unit || null,
          notes: completion.notes || null,
        }),
      });
      setCompletionTaskId(null);
      setCompletion({ duration_minutes: "", worker_id: completion.worker_id, quantity_used: "", unit: "", notes: "" });
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

  function changeQuickSaleHarvest(event) {
    const harvestId = event.target.value;
    const item = inventory.find((entry) => String(entry.harvest_id) === String(harvestId));
    setQuickSaleForm({ ...quickSaleForm, harvest_id: harvestId, price_per_kg_eur: item?.suggested_price_per_kg_eur || "" });
  }

  function addQuickSaleItem(event) {
    event.preventDefault(); clearMessages();
    const inventoryItem = inventory.find((item) => String(item.harvest_id) === String(quickSaleForm.harvest_id));
    const quantity = Number(quickSaleForm.quantity_kg);
    const price = Number(quickSaleForm.price_per_kg_eur);
    if (!inventoryItem || !Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(price) || price <= 0) {
      setError("Izberite artikel ter vnesite veljavno količino in ceno."); return;
    }
    if (quickSaleCart.some((item) => item.harvest_id === inventoryItem.harvest_id)) {
      setError("Ta zaloga je že v košarici. Postavko odstranite in jo dodajte znova."); return;
    }
    if (quantity > inventoryItem.available_kg) {
      setError(`Na voljo je največ ${inventoryItem.available_kg.toFixed(2)} kg.`); return;
    }
    setQuickSaleCart([...quickSaleCart, {
      harvest_id: inventoryItem.harvest_id,
      crop: inventoryItem.crop,
      variety: inventoryItem.variety,
      bed: inventoryItem.bed,
      quality: inventoryItem.quality,
      quantity_kg: quantity,
      price_per_kg_eur: price,
      line_total_eur: Number((quantity * price).toFixed(2)),
    }]);
    setQuickSaleForm({ ...quickSaleForm, quantity_kg: "" });
  }

  async function createQuickSale() {
    if (quickSaleCart.length === 0) { setError("V košarico dodajte vsaj en artikel."); return; }
    clearMessages();
    try {
      const items = quickSaleCart.map(({ harvest_id, quantity_kg, price_per_kg_eur }) => ({ harvest_id, quantity_kg, price_per_kg_eur }));
      const data = await apiRequest("/api/retail-sales", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ customer_id: quickSaleForm.customer_id ? Number(quickSaleForm.customer_id) : null, sale_date: quickSaleForm.sale_date, payment_method: quickSaleForm.payment_method, items }) });
      setQuickSaleCart([]); setQuickSaleForm({ ...quickSaleForm, quantity_kg: "" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function saveProductPrice(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest(`/api/price-list/${priceForm.crop_id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ quality: priceForm.quality, price_per_kg_eur: Number(priceForm.price_per_kg_eur) }) });
      setPriceForm({ ...priceForm, price_per_kg_eur: "" }); setNotice(data.message); await loadData();
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

  async function saveInvoiceProfile(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/invoice-profile", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(invoiceProfile) });
      setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function issueInvoice(sourceType, sourceId) {
    if (!window.confirm("Izdani račun se arhivira in ga pozneje ni mogoče spreminjati. Nadaljujem?")) return;
    clearMessages();
    try {
      const data = await apiRequest("/api/invoices", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_type: sourceType, source_id: sourceId, issued_on: today }) });
      setNotice(data.message); await loadData(); setView("invoices");
    } catch (requestError) { setError(requestError.message); }
  }

  async function openInvoicePdf(invoiceId) {
    clearMessages();
    try { await downloadProtectedFile(`/api/invoices/${invoiceId}/pdf`, `racun-${invoiceId}.pdf`, true); }
    catch (requestError) { setError(requestError.message); }
  }

  async function saveFiscalConfirmation(invoiceId, creditNoteId = null) {
    const eor = window.prompt("Vpišite EOR, ki ga je vrnil sistem davčnega potrjevanja:");
    if (!eor) return;
    const zoi = window.prompt("Vpišite ZOI (če ga imate):") || null;
    clearMessages();
    const path = creditNoteId ? `/api/credit-notes/${creditNoteId}/fiscal-confirmation` : `/api/invoices/${invoiceId}/fiscal-confirmation`;
    try {
      const data = await apiRequest(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ eor, zoi }) });
      setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function issueCreditNote(invoiceId) {
    const reason = window.prompt("Razlog za celotni dobropis:");
    if (!reason) return;
    if (!window.confirm("Dobropis bo nespremenljivo arhiviran, prvotni račun pa bo ostal v zgodovini. Nadaljujem?")) return;
    clearMessages();
    try {
      const data = await apiRequest(`/api/invoices/${invoiceId}/credit-notes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ issued_on: today, reason }) });
      setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function recordRefund(creditNote, invoice) {
    const amountInput = window.prompt(
      `Znesek vračila (največ ${creditNote.refundable_eur.toFixed(2)} €):`,
      creditNote.refundable_eur.toFixed(2),
    );
    if (amountInput === null) return;
    const amount = Number(amountInput.replace(",", "."));
    if (!Number.isFinite(amount) || amount <= 0) {
      setError("Vnesite veljaven znesek vračila.");
      return;
    }
    const methodInput = window.prompt(
      "Način vračila: gotovina, kartica ali nakazilo",
      paymentLabelForPrompt(invoice.payment_method),
    );
    if (methodInput === null) return;
    const paymentMethod = {
      gotovina: "cash",
      cash: "cash",
      kartica: "card",
      card: "card",
      nakazilo: "bank_transfer",
      bank_transfer: "bank_transfer",
    }[methodInput.trim().toLowerCase()];
    if (!paymentMethod) {
      setError("Način vračila mora biti gotovina, kartica ali nakazilo.");
      return;
    }
    const notes = window.prompt("Opomba k vračilu (neobvezno):") || null;
    if (!window.confirm(`Evidentiram dejansko vračilo ${amount.toFixed(2)} €?`)) return;
    clearMessages();
    try {
      const data = await apiRequest(`/api/credit-notes/${creditNote.id}/refunds`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refund_date: today, amount_eur: amount, payment_method: paymentMethod, notes }),
      });
      setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  function paymentLabelForPrompt(method) {
    return ({ cash: "gotovina", card: "kartica", bank_transfer: "nakazilo" }[method] || "nakazilo");
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

  async function closeBusinessDay(event) {
    event.preventDefault(); clearMessages();
    const openingCash = Number(dayCloseForm.opening_cash_eur);
    const countedCash = Number(dayCloseForm.counted_cash_eur);
    if (!Number.isFinite(openingCash) || openingCash < 0 || !Number.isFinite(countedCash) || countedCash < 0) {
      setError("Vnesite veljavno začetno in prešteto gotovino."); return;
    }
    if (!window.confirm(`Zaključim poslovni dan ${dayCloseForm.business_date}? Poznejši denarni vnosi za ta datum ne bodo več mogoči.`)) return;
    try {
      const data = await apiRequest("/api/day-closes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_date: dayCloseForm.business_date,
          opening_cash_eur: openingCash,
          counted_cash_eur: countedCash,
          notes: dayCloseForm.notes || null,
        }),
      });
      setDayClosePreview({ closed: true, ...data });
      setDayCloseForm({ ...dayCloseForm, counted_cash_eur: "", notes: "" });
      setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function createFarmExpense(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/farm-expenses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...farmExpenseForm,
          amount_eur: Number(farmExpenseForm.amount_eur),
          supplier: farmExpenseForm.supplier || null,
          reference: farmExpenseForm.reference || null,
        }),
      });
      setFarmExpenseForm({ ...farmExpenseForm, amount_eur: "", supplier: "", reference: "", description: "" });
      setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function restoreData(event) {
    event.preventDefault(); clearMessages();
    if (!restoreFile) { setError("Najprej izberite GrowMaster varnostno kopijo."); return; }
    if (restoreConfirmation !== "OBNOVI") { setError('Za potrditev vpišite "OBNOVI".'); return; }
    if (!window.confirm("Obnovim podatke iz izbrane kopije? Trenutno stanje bo pred tem samodejno varnostno shranjeno.")) return;
    try {
      const response = await apiFetch("/api/system/backups/restore?confirmation=OBNOVI", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: await restoreFile.text(),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Obnovitev ni uspela.");
      setRestoreFile(null); setRestoreConfirmation(""); setNotice(`${data.message} Povratna kopija: ${data.safety_backup}`); await loadData();
      const [safetyData, readinessData] = await Promise.all([apiRequest("/api/system/data-safety"), apiRequest("/api/system/readiness")]);
      setDataSafety(safetyData); setReadiness(readinessData);
    } catch (requestError) { setError(requestError.message); }
  }

  async function createSupplier(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/suppliers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(supplierForm) });
      setSupplierForm({ name: "", tax_number: "", email: "", phone: "" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function createSupplyItem(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/supply-items", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...supplyItemForm, opening_stock: Number(supplyItemForm.opening_stock), reorder_level: Number(supplyItemForm.reorder_level) }) });
      setSupplyItemForm({ name: "", category: supplyItemForm.category, unit: supplyItemForm.unit, opening_stock: "0", reorder_level: "0" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  function addPurchaseItem(event) {
    event.preventDefault(); clearMessages();
    const supplyItem = supplyItems.find((item) => String(item.id) === String(purchaseForm.supply_item_id));
    const quantity = Number(purchaseForm.quantity);
    const price = Number(purchaseForm.unit_price_eur);
    if (!supplyItem || !Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(price) || price <= 0) {
      setError("Izberite material ter vnesite veljavno količino in ceno."); return;
    }
    if (purchaseCart.some((item) => item.supply_item_id === supplyItem.id)) {
      setError("Ta material je že v naročilu."); return;
    }
    setPurchaseCart([...purchaseCart, { supply_item_id: supplyItem.id, name: supplyItem.name, unit: supplyItem.unit, quantity, unit_price_eur: price, line_total_eur: Number((quantity * price).toFixed(2)) }]);
    setPurchaseForm({ ...purchaseForm, quantity: "", unit_price_eur: "" });
  }

  async function createPurchaseOrder() {
    if (!purchaseForm.supplier_id) { setError("Najprej dodajte in izberite dobavitelja."); return; }
    if (purchaseCart.length === 0) { setError("V naročilo dodajte vsaj en material."); return; }
    clearMessages();
    try {
      const items = purchaseCart.map(({ supply_item_id, quantity, unit_price_eur }) => ({ supply_item_id, quantity, unit_price_eur }));
      const data = await apiRequest("/api/purchase-orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ supplier_id: Number(purchaseForm.supplier_id), order_date: purchaseForm.order_date, expected_date: purchaseForm.expected_date || null, payment_method: purchaseForm.payment_method, notes: purchaseForm.notes || null, items }) });
      setPurchaseCart([]); setPurchaseForm({ ...purchaseForm, quantity: "", unit_price_eur: "", notes: "" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function receivePurchaseOrder(purchaseOrder) {
    const receivedOn = window.prompt("Datum prevzema:", today);
    if (!receivedOn) return;
    if (!window.confirm(`Prevzamem ${purchaseOrder.number} in povečam zalogo vseh postavk?`)) return;
    clearMessages();
    try {
      const data = await apiRequest(`/api/purchase-orders/${purchaseOrder.id}/receive`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ received_on: receivedOn }) });
      setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function cancelPurchaseOrder(purchaseOrder) {
    if (!window.confirm(`Prekličem ${purchaseOrder.number}?`)) return;
    clearMessages();
    try {
      const data = await apiRequest(`/api/purchase-orders/${purchaseOrder.id}/cancel`, { method: "POST" });
      setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function createSupplyUsage(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/supply-usages", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ supply_item_id: Number(supplyUsageForm.supply_item_id), bed_id: Number(supplyUsageForm.bed_id), planting_id: supplyUsageForm.planting_id ? Number(supplyUsageForm.planting_id) : null, usage_date: supplyUsageForm.usage_date, quantity: Number(supplyUsageForm.quantity), unit_cost_eur: supplyUsageForm.unit_cost_eur ? Number(supplyUsageForm.unit_cost_eur) : null, notes: supplyUsageForm.notes || null }) });
      setSupplyUsageForm({ ...supplyUsageForm, quantity: "", unit_cost_eur: "", notes: "" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  function beginSupplierPayment(order) {
    clearMessages(); setSupplierPaymentOrderId(order.id);
    setSupplierPaymentForm({ payment_date: today < order.order_date ? order.order_date : today, amount_eur: order.outstanding_eur.toFixed(2), payment_method: order.payment_method, notes: "" });
  }

  async function recordSupplierPayment(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest(`/api/purchase-orders/${supplierPaymentOrderId}/payments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...supplierPaymentForm, amount_eur: Number(supplierPaymentForm.amount_eur) }) });
      setSupplierPaymentOrderId(null); setSupplierPaymentForm({ payment_date: today, amount_eur: "", payment_method: "bank_transfer", notes: "" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function createWorker(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/workers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: workerForm.name, role: workerForm.role || null, hourly_rate_eur: Number(workerForm.hourly_rate_eur) }) });
      setWorkerForm({ name: "", role: "", hourly_rate_eur: "" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
  }

  async function createLaborEntry(event) {
    event.preventDefault(); clearMessages();
    try {
      const data = await apiRequest("/api/labor-entries", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ worker_id: Number(laborForm.worker_id), bed_id: laborForm.bed_id ? Number(laborForm.bed_id) : null, planting_id: laborForm.planting_id ? Number(laborForm.planting_id) : null, work_date: laborForm.work_date, duration_minutes: Number(laborForm.duration_minutes), hourly_rate_eur: laborForm.hourly_rate_eur === "" ? null : Number(laborForm.hourly_rate_eur), description: laborForm.description }) });
      setLaborForm({ ...laborForm, duration_minutes: "", hourly_rate_eur: "", description: "" }); setNotice(data.message); await loadData();
    } catch (requestError) { setError(requestError.message); }
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

  async function createGredicnikPlan(payload) {
    clearMessages();
    try {
      const data = await apiRequest("/api/plans", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      setNotice(`${data.message} Izračun Gredičnika je shranjen v načrt.${data.warnings.length ? ` Opozorila: ${data.warnings.join(" ")}` : ""}`);
      await loadData();
      setView("planning");
      window.scrollTo({ top: 0, behavior: "smooth" });
      return true;
    } catch (requestError) {
      setError(requestError.message);
      return false;
    }
  }

  async function activatePlan(planId, overrideRotation = false) {
    clearMessages();
    const response = await apiFetch(`/api/plans/${planId}/activate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ override_rotation: overrideRotation }) });
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

  const primaryNavigation = [
    ["dashboard", "Domov", "⌂"],
    ["beds", "Gredice", "▦"],
    ["tasks", "Opravila", "✓"],
    ["orders", "Prodaja", "▤"],
  ];
  const moreNavigation = [
    ["planting", "Setev", "+"],
    ["labor", "Delo", "◷"],
    ["economics", "Žetev €", "€"],
    ["profitability", "Analitika", "◎"],
    ["expenses", "Stroški", "−"],
    ["invoices", "Računi", "R"],
    ["reports", "Poročila prodaje", "Σ"],
    ["receivables", "Terjatve", "↔"],
    ["cashflow", "Denar", "◒"],
    ["closing", "Zaključek", "✓"],
    ["purchasing", "Nabava", "↓"],
    ["gredicnik", "Gredičnik", "▥"],
    ["planning", "Plan", "◫"],
    ["crops", "Zelenjava in sorte", "♧"],
    ["data", "Podatki", "⬇"],
    ["settings", "Nastavitve", "⚙"],
  ];
  const moreMenuActive = moreNavigation.some(([key]) => key === view);

  function openView(key) {
    setView(key);
    setMoreMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function changeServer() {
    forgetServer();
    setAuth({ loading: true, configured: false, authenticated: false, display_name: null, session_days: 30, demo_data_available: false });
    setServerReady(false);
    clearMessages();
  }

  async function installWebApp() {
    if (!installPrompt) return;
    await installPrompt.prompt();
    setInstallPrompt(null);
  }

  if (!serverReady) {
    return <ConnectionView onConnected={(serverUrl) => { saveServerUrl(serverUrl); setServerReady(true); }} />;
  }

  if (auth.loading || !auth.authenticated) {
    return <AuthenticationView auth={auth} form={authForm} setForm={setAuthForm} submit={submitAuthentication} error={error} changeServer={isNativeApp ? changeServer : null} serverUrl={configuredServerUrl()} />;
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Lokalno upravljanje kmetije</p>
          <h1>🌱 GrowMaster</h1>
          <p>{farmProfile.farm_name ? `${farmProfile.farm_name} · gredice, setve in dnevno delo.` : "Gredice, setve in dnevno delo na enem mestu."}</p>
        </div>
        <div className="account-summary">
          <span className={`connection-pill ${online ? "online" : "offline"}`}>{online ? "● POVEZANO" : "● BREZ POVEZAVE"}</span>
          <span className="status-pill">1.20.1</span>
          <span>Prijavljen: <strong>{auth.display_name}</strong></span>
          {installPrompt && <button type="button" onClick={installWebApp}>NAMESTI APLIKACIJO</button>}
          {isNativeApp && <button type="button" onClick={changeServer}>STREŽNIK</button>}
          <button type="button" onClick={logout}>ODJAVA</button>
        </div>
      </header>

      <nav className="main-nav" aria-label="Glavna navigacija">
        {primaryNavigation.map(([key, label, icon]) => (
          <button key={key} className={view === key ? "active" : ""} onClick={() => openView(key)}>
            <span>{icon}</span>{label}
          </button>
        ))}
        <button className={moreMenuActive || moreMenuOpen ? "active" : ""} onClick={() => setMoreMenuOpen((current) => !current)} aria-expanded={moreMenuOpen} aria-controls="more-navigation">
          <span>•••</span>Več
        </button>
      </nav>

      {moreMenuOpen && (
        <>
          <button type="button" className="more-menu-backdrop" aria-label="Zapri meni" onClick={() => setMoreMenuOpen(false)} />
          <section className="more-menu" id="more-navigation" aria-label="Vsi moduli">
            <div className="more-menu-heading"><div><p className="eyebrow">Vsi moduli</p><h2>Kam želiš?</h2></div><button type="button" className="icon-button" aria-label="Zapri meni" onClick={() => setMoreMenuOpen(false)}>✕</button></div>
            <div className="more-menu-grid">
              {moreNavigation.map(([key, label, icon]) => (
                <button type="button" key={key} className={view === key ? "active" : ""} onClick={() => openView(key)}>
                  <span>{icon}</span><strong>{label}</strong>
                </button>
              ))}
            </div>
          </section>
        </>
      )}

      {!online && <div className="offline-banner">Brez povezave. Pregled odprtega zaslona ostane na voljo, novih vnosov pa trenutno ni mogoče varno shraniti.</div>}

      {notice && <div className="message success">✓ {notice}</div>}
      {error && <div className="message error">⚠ {error}</div>}

      {view === "dashboard" && (
        <DashboardView dashboard={dashboard} beds={beds} setView={setView}
          taskReview={taskReview} selectedReviewKeys={selectedReviewKeys}
          toggleReviewSuggestion={toggleReviewSuggestion} selectAllReviewSuggestions={selectAllReviewSuggestions}
          applyTaskReview={applyTaskReview} reviewApplying={reviewApplying} />
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
          bedSizeForm={bedSizeForm}
          setBedSizeForm={setBedSizeForm}
          updateBedSize={updateBedSize}
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
          suggestions={plantingSuggestions}
          suggestionsLoading={suggestionsLoading}
          requestSuggestions={requestPlantingSuggestions}
          applySuggestion={applyPlantingSuggestion}
          clearSuggestions={() => setPlantingSuggestions(null)}
        />
      )}

      {view === "tasks" && (
        <TasksView
          tasks={tasks}
          beds={beds}
          workers={workers}
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
      {view === "labor" && (
        <LaborView workers={workers} beds={beds} plantings={plantings} data={laborReport}
          start={laborStart} setStart={setLaborStart} end={laborEnd} setEnd={setLaborEnd}
          workerForm={workerForm} setWorkerForm={setWorkerForm} createWorker={createWorker}
          laborForm={laborForm} setLaborForm={setLaborForm} createLaborEntry={createLaborEntry} />
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
      {view === "profitability" && (
        <ProfitabilityView data={profitabilityReport}
          start={profitabilityStart} setStart={setProfitabilityStart}
          end={profitabilityEnd} setEnd={setProfitabilityEnd} />
      )}
      {view === "expenses" && (
        <FarmExpensesView expenses={farmExpenses} form={farmExpenseForm} setForm={setFarmExpenseForm}
          createExpense={createFarmExpense} start={profitabilityStart} setStart={setProfitabilityStart}
          end={profitabilityEnd} setEnd={setProfitabilityEnd} />
      )}
      {view === "orders" && (
        <OrdersView inventory={inventory} crops={crops} customers={customers} orders={orders}
          customerForm={customerForm} setCustomerForm={setCustomerForm} createCustomer={createCustomer}
          orderForm={orderForm} setOrderForm={setOrderForm} createOrder={createOrder}
          changeOrderStatus={changeOrderStatus} openOrderDocument={openOrderDocument}
          issueInvoice={issueInvoice} openInvoicePdf={openInvoicePdf}
          document={document} setDocument={setDocument} retailSales={retailSales}
          quickSaleForm={quickSaleForm} setQuickSaleForm={setQuickSaleForm} createQuickSale={createQuickSale} openRetailDocument={openRetailDocument}
          quickSaleCart={quickSaleCart} addQuickSaleItem={addQuickSaleItem} changeQuickSaleHarvest={changeQuickSaleHarvest}
          removeQuickSaleItem={(harvestId) => setQuickSaleCart(quickSaleCart.filter((item) => item.harvest_id !== harvestId))}
          priceList={priceList} priceForm={priceForm} setPriceForm={setPriceForm} saveProductPrice={saveProductPrice}
          salesSettings={salesSettings} setSalesSettings={setSalesSettings} saveSalesSettings={saveSalesSettings} />
      )}
      {view === "invoices" && (
        <InvoicesView invoices={invoices} profile={invoiceProfile} setProfile={setInvoiceProfile}
          saveProfile={saveInvoiceProfile} openPdf={openInvoicePdf}
          confirmFiscal={saveFiscalConfirmation} issueCreditNote={issueCreditNote}
          recordRefund={recordRefund} />
      )}
      {view === "reports" && (
        <SalesReportView report={salesReport} start={reportStart} setStart={setReportStart} end={reportEnd} setEnd={setReportEnd} />
      )}
      {view === "receivables" && (
        <ReceivablesView data={receivables} asOf={receivablesAsOf} setAsOf={setReceivablesAsOf} includePaid={includePaidReceivables} setIncludePaid={setIncludePaidReceivables} paymentOrderId={paymentOrderId} beginPayment={beginPayment} cancelPayment={() => setPaymentOrderId(null)} paymentForm={paymentForm} setPaymentForm={setPaymentForm} recordPayment={recordPayment} />
      )}
      {view === "cashflow" && (
        <CashFlowView data={cashFlow} start={cashFlowStart} setStart={setCashFlowStart} end={cashFlowEnd} setEnd={setCashFlowEnd} />
      )}
      {view === "closing" && (
        <DayCloseView closes={dayCloses} preview={dayClosePreview} form={dayCloseForm} setForm={setDayCloseForm} closeDay={closeBusinessDay} />
      )}
      {view === "purchasing" && (
        <PurchasingView suppliers={suppliers} supplyItems={supplyItems} purchaseOrders={purchaseOrders} supplyUsages={supplyUsages} beds={beds} plantings={plantings}
          supplierForm={supplierForm} setSupplierForm={setSupplierForm} createSupplier={createSupplier}
          supplyItemForm={supplyItemForm} setSupplyItemForm={setSupplyItemForm} createSupplyItem={createSupplyItem}
          purchaseForm={purchaseForm} setPurchaseForm={setPurchaseForm} purchaseCart={purchaseCart}
          addPurchaseItem={addPurchaseItem} removePurchaseItem={(itemId) => setPurchaseCart(purchaseCart.filter((item) => item.supply_item_id !== itemId))}
          createPurchaseOrder={createPurchaseOrder} receivePurchaseOrder={receivePurchaseOrder} cancelPurchaseOrder={cancelPurchaseOrder}
          supplyUsageForm={supplyUsageForm} setSupplyUsageForm={setSupplyUsageForm} createSupplyUsage={createSupplyUsage}
          supplierPaymentOrderId={supplierPaymentOrderId} beginSupplierPayment={beginSupplierPayment} cancelSupplierPayment={() => setSupplierPaymentOrderId(null)}
          supplierPaymentForm={supplierPaymentForm} setSupplierPaymentForm={setSupplierPaymentForm} recordSupplierPayment={recordSupplierPayment} />
      )}
      {view === "planning" && (
        <PlanningView crops={crops} beds={beds} plans={plans} calendar={planningCalendar} forecast={forecast}
          form={planForm} setForm={setPlanForm} selectedCrop={selectedPlanCrop} changeCrop={changePlanCrop} createPlan={createPlan}
          activatePlan={activatePlan} cancelPlan={cancelPlan} start={planStart} setStart={setPlanStart} end={planEnd} setEnd={setPlanEnd} />
      )}
      {view === "gredicnik" && (
        <GredicnikView crops={crops} beds={beds} savePlan={createGredicnikPlan} />
      )}
      {view === "crops" && (
        <CropCatalogView crops={crops} cropForm={cropForm} setCropForm={setCropForm} createCrop={createCrop}
          varietyForm={varietyForm} setVarietyForm={setVarietyForm} createVariety={createVariety} />
      )}
      {view === "data" && (
        <DataSafetyView status={dataSafety} readiness={readiness} restoreFile={restoreFile} setRestoreFile={setRestoreFile}
          confirmation={restoreConfirmation} setConfirmation={setRestoreConfirmation} restoreData={restoreData} />
      )}
      {view === "settings" && (
        <SettingsView profile={farmProfile} setProfile={setFarmProfile} saveProfile={saveFarmProfile}
          account={account} accountForm={accountForm} setAccountForm={setAccountForm}
          passwordForm={passwordForm} setPasswordForm={setPasswordForm} updateAccount={updateAccount} changePassword={changePassword} />
      )}
    </main>
  );
}

function DashboardView({ dashboard, beds, setView, taskReview, selectedReviewKeys, toggleReviewSuggestion, selectAllReviewSuggestions, applyTaskReview, reviewApplying }) {
  const emptyBeds = beds.filter((bed) => bed.status === "empty").length;
  const allSuggestionsSelected = Boolean(taskReview?.suggestions.length) && selectedReviewKeys.length === taskReview.suggestions.length;
  return (
    <>
      <section className="metric-grid">
        <article className="metric-card"><span>Današnja opravila</span><strong>{dashboard?.tasks_total || 0}</strong><small>{dashboard?.tasks_completed || 0} opravljenih</small></article>
        <article className="metric-card"><span>Aktivne gredice</span><strong>{dashboard?.active_beds || 0}</strong><small>{emptyBeds} praznih</small></article>
        <article className="metric-card"><span>Naslednja žetev</span><strong>{dashboard?.next_harvest?.bed || "—"}</strong><small>{dashboard?.next_harvest ? `${dashboard.next_harvest.crop} · ${dashboard.next_harvest.expected_harvest_date}` : "Ni aktivnih setev"}</small></article>
      </section>
      <section className="panel smart-review-panel">
        <div className="section-heading smart-review-heading">
          <div><p className="eyebrow">Samodejno · lokalno</p><h2>Pametni dnevni pregled</h2><p className="muted">GrowMaster pregleda vse gredice in pripravi samo manjkajoča opravila za naslednjih 7 dni.</p></div>
          <span>{taskReview?.reviewed_beds ?? beds.length} pregledanih gredic</span>
        </div>
        {!taskReview ? <p className="empty-state">Pregledujem gredice …</p> : <>
          <div className="smart-review-metrics">
            <article><span>Aktivnih</span><strong>{taskReview.active_beds}</strong></article>
            <article className={taskReview.overdue_count ? "attention" : ""}><span>Zamujenih</span><strong>{taskReview.overdue_count}</strong></article>
            <article><span>Predlogov</span><strong>{taskReview.suggestion_count}</strong></article>
          </div>
          {taskReview.overdue_count > 0 && <div className="review-overdue">
            <div><strong>Najprej uredi zamujena opravila</strong><span>{taskReview.overdue_count} opravil že čaka na izvedbo.</span></div>
            <div className="review-overdue-list">{taskReview.overdue_tasks.slice(0, 5).map((task) => <span key={task.id}><b>{task.bed || "Splošno"}</b>{task.title}<time>{task.due_date}</time></span>)}</div>
            {taskReview.overdue_count > 5 && <small>in še {taskReview.overdue_count - 5} opravil</small>}
            <button type="button" className="text-button" onClick={() => setView("tasks")}>ODPRI OPRAVILA →</button>
          </div>}
          {taskReview.suggestions.length > 0 ? <>
            <div className="review-actions-top"><span>Izberi predloge, ki jih želiš dodati.</span><button type="button" className="text-button" onClick={selectAllReviewSuggestions}>{allSuggestionsSelected ? "ODZNAČI VSE" : "IZBERI VSE"}</button></div>
            <div className="review-suggestion-list">
              {taskReview.suggestions.map((suggestion) => <label className="review-suggestion" key={suggestion.key}>
                <input type="checkbox" checked={selectedReviewKeys.includes(suggestion.key)} onChange={() => toggleReviewSuggestion(suggestion.key)} />
                <span className={`priority-dot ${suggestion.priority}`} />
                <span className="review-suggestion-main"><strong>{suggestion.title}</strong><small>Gredica {suggestion.bed} · {suggestion.stage} · rok {suggestion.due_date}</small><em>{suggestion.reason}</em></span>
              </label>)}
            </div>
            <div className="review-create-row"><small>{selectedReviewKeys.length} izbranih · pred shranjevanjem se predlogi še enkrat preverijo</small><button type="button" className="primary-button" disabled={!selectedReviewKeys.length || reviewApplying} onClick={applyTaskReview}>{reviewApplying ? "USTVARJAM …" : `USTVARI IZBRANA OPRAVILA (${selectedReviewKeys.length})`}</button></div>
          </> : <div className="review-all-clear"><strong>✓ Za zdaj je vse pokrito.</strong><span>Ni novih predlogov za naslednjih 7 dni.</span></div>}
          <p className="smart-review-note">{taskReview.note}</p>
        </>}
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

function BedsView({ beds, bedForm, setBedForm, createBed, openBed, selectedBed, setSelectedBed, bedSizeForm, setBedSizeForm, updateBedSize, finishPlanting }) {
  const previewArea = Number(bedSizeForm.width_m) * Number(bedSizeForm.length_m);
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
          <form className="bed-size-form" onSubmit={updateBedSize}>
            <div><p className="eyebrow">Mere gredice</p><strong>Popravi velikost</strong></div>
            <label>Širina (m)<input type="number" step="0.01" min="0.01" max="100" value={bedSizeForm.width_m} onChange={(event) => setBedSizeForm({ ...bedSizeForm, width_m: event.target.value })} required /></label>
            <label>Dolžina (m)<input type="number" step="0.01" min="0.01" max="1000" value={bedSizeForm.length_m} onChange={(event) => setBedSizeForm({ ...bedSizeForm, length_m: event.target.value })} required /></label>
            <div className="bed-area-preview"><span>Nova površina</span><strong>{Number.isFinite(previewArea) ? previewArea.toFixed(2) : "—"} m²</strong></div>
            <button className="secondary-button" type="submit">SHRANI VELIKOST</button>
          </form>
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

function VarietyCatalogItem({ variety }) {
  const actionLabel = variety.planting_method === "transplant" ? "Presajanje" : "Setev";
  return <span className={variety.source_name ? "supplier-variety" : ""}>
    <strong>{variety.name}</strong>
    {variety.composition && <em className="variety-composition"><b>Sestava:</b> {variety.composition}</em>}
    <small>Pomlad {variety.days_spring} · Poletje {variety.days_summer}</small>
    <small>Jesen {variety.days_autumn} · Zima {variety.days_winter} dni</small>
    {variety.source_name && <small className="variety-supplier-badge">Izbrano za slovenske razmere</small>}
    {variety.source_name && <details className="variety-details"><summary>Podrobnosti in vir</summary>
      {variety.traits && <em className="variety-catalog-note">{variety.traits}</em>}
      {variety.slovenia_note && <em className="variety-slovenia-note"><b>Slovenija:</b> {variety.slovenia_note}</em>}
      {variety.seed_forms && <small>Oblike semena: {variety.seed_forms}</small>}
      {variety.days_baby && <small>Baby leaf oziroma baby pridelek: {variety.days_baby} dni</small>}
      {variety.outdoor_months && <small><b>{actionLabel} na prostem:</b> {formatPlantingMonths(variety.outdoor_months)}</small>}
      {variety.protected_months && <small><b>{actionLabel} v tunelu:</b> {formatPlantingMonths(variety.protected_months)}</small>}
      {(variety.heat_tolerance || variety.cold_tolerance) && <small>Vročina: {toleranceLabel(variety.heat_tolerance)} · mraz: {toleranceLabel(variety.cold_tolerance)}</small>}
      {variety.succession_interval_days && <small>Zaporedna setev: približno vsakih {variety.succession_interval_days} dni</small>}
      {variety.planting_calendar_note && <em className="variety-calendar-note">{variety.planting_calendar_note}</em>}
      {variety.source_url && <a className="variety-source" href={variety.source_url} target="_blank" rel="noreferrer">Vir: {variety.source_name} ↗</a>}
      {variety.calendar_source_url && variety.calendar_source_url !== variety.source_url && <a className="variety-source" href={variety.calendar_source_url} target="_blank" rel="noreferrer">Vir koledarja ↗</a>}
    </details>}
  </span>;
}

function CropCatalogView({ crops, cropForm, setCropForm, createCrop, varietyForm, setVarietyForm, createVariety }) {
  const [catalogQuery, setCatalogQuery] = useState("");
  const normalizedQuery = catalogQuery.trim().toLocaleLowerCase("sl");
  const visibleCrops = normalizedQuery ? crops.filter((crop) => [crop.name, crop.family, crop.category, ...crop.varieties.flatMap((variety) => [variety.name, variety.composition, variety.source_name, variety.seed_forms, variety.traits, variety.slovenia_note].filter(Boolean))].some((value) => value.toLocaleLowerCase("sl").includes(normalizedQuery))) : crops;
  const supplierVarietyCount = crops.reduce((count, crop) => count + crop.varieties.filter((variety) => variety.source_name).length, 0);
  const categoryOrder = new Map([["Domača", 0], ["Azijska", 1], ["Indijska", 2], ["Baby leaf", 3]]);
  const catalogGroups = Object.entries(visibleCrops.reduce((groups, crop) => {
    const category = crop.category || "Drugo";
    return { ...groups, [category]: [...(groups[category] || []), crop] };
  }, {})).sort(([left], [right]) => (categoryOrder.get(left) ?? 99) - (categoryOrder.get(right) ?? 99) || left.localeCompare(right, "sl"));
  return (
    <>
      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">Lastni šifrant</p><h2>Zelenjava in sorte</h2><p className="muted">Dodani vnosi so takoj na voljo pri setvi, načrtovanju, žetvi in ceniku.</p></div><span>{crops.length} vrst · {supplierVarietyCount} preverjenih sort</span></div>
        <div className="crop-catalog-forms">
          <form className="catalog-form" onSubmit={createCrop}>
            <div><p className="eyebrow">Nova zelenjava</p><h3>Dodaj vrsto zelenjave</h3></div>
            <label>Ime<input value={cropForm.name} onChange={(event) => setCropForm({ ...cropForm, name: event.target.value })} placeholder="npr. Paradižnik" required /></label>
            <label>Rastlinska družina<input value={cropForm.family} onChange={(event) => setCropForm({ ...cropForm, family: event.target.value })} placeholder="npr. Solanaceae" required /></label>
            <label>Kategorija<input value={cropForm.category} onChange={(event) => setCropForm({ ...cropForm, category: event.target.value })} placeholder="npr. Plodovke" required /></label>
            <button className="primary-button" type="submit">DODAJ ZELENJAVO</button>
          </form>

          <form className="catalog-form" onSubmit={createVariety}>
            <div><p className="eyebrow">Nova sorta</p><h3>Dodaj sorto izbrani zelenjavi</h3></div>
            <label>Zelenjava<select value={varietyForm.crop_id} onChange={(event) => setVarietyForm({ ...varietyForm, crop_id: event.target.value })} required disabled={!crops.length}><option value="">Izberi zelenjavo</option>{crops.map((crop) => <option key={crop.id} value={crop.id}>{crop.name}</option>)}</select></label>
            <label>Ime sorte<input value={varietyForm.name} onChange={(event) => setVarietyForm({ ...varietyForm, name: event.target.value })} placeholder="npr. Volovsko srce" required /></label>
            <div className="seasonal-maturity-fields">
              <label>Pomlad (dni)<input type="number" min="1" max="730" value={varietyForm.days_spring} onChange={(event) => setVarietyForm({ ...varietyForm, days_spring: event.target.value })} placeholder="npr. 45" required /></label>
              <label>Poletje (dni)<input type="number" min="1" max="730" value={varietyForm.days_summer} onChange={(event) => setVarietyForm({ ...varietyForm, days_summer: event.target.value })} placeholder="npr. 35" required /></label>
              <label>Jesen (dni)<input type="number" min="1" max="730" value={varietyForm.days_autumn} onChange={(event) => setVarietyForm({ ...varietyForm, days_autumn: event.target.value })} placeholder="npr. 55" required /></label>
              <label>Zima (dni)<input type="number" min="1" max="730" value={varietyForm.days_winter} onChange={(event) => setVarietyForm({ ...varietyForm, days_winter: event.target.value })} placeholder="npr. 75" required /></label>
            </div>
            <label>Sestava mešanice (neobvezno)<textarea maxLength="1000" value={varietyForm.composition} onChange={(event) => setVarietyForm({ ...varietyForm, composition: event.target.value })} placeholder="Npr. mizuna, tatsoi, pak choi ..." /></label>
            <button className="primary-button" type="submit" disabled={!crops.length}>DODAJ SORTO</button>
          </form>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">Pregled šifranta</p><h2>Vsa zelenjava</h2></div><label className="catalog-search">Išči<input type="search" value={catalogQuery} onChange={(event) => setCatalogQuery(event.target.value)} placeholder="Zelenjava ali sorta" /></label></div>
        <div className="crop-catalog-groups">
          {catalogGroups.map(([category, categoryCrops]) => (
            <section className="crop-category-section" key={category}>
              <div className="crop-category-heading"><h3>{category}</h3><span>{categoryCrops.length} vrst</span></div>
              <div className="crop-catalog-grid">
                {categoryCrops.map((crop) => (
                  <article className="crop-catalog-card" key={crop.id}>
                    <div><h3>{crop.name}</h3><span>{crop.family}</span></div>
                    <div className="variety-list">
                      {crop.varieties.map((variety) => <VarietyCatalogItem key={variety.id} variety={variety} />)}
                      {!crop.varieties.length && <small>Sorta še ni dodana.</small>}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}
          {!crops.length && <p className="empty-state">Dodaj prvo zelenjavo in nato njeno sorto.</p>}
          {crops.length > 0 && !visibleCrops.length && <p className="empty-state">Za ta iskalni niz ni zadetkov.</p>}
        </div>
      </section>
    </>
  );
}

function PlantingView({ crops, beds, plantings, form, setForm, selectedCrop, changeCrop, savePlanting, rotationWarning, setRotationWarning, suggestions, suggestionsLoading, requestSuggestions, applySuggestion, clearSuggestions }) {
  return (
    <>
      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">Načrt setve</p><h2>Dodaj novo setev</h2></div></div>
        <form className="planting-form" onSubmit={(event) => { event.preventDefault(); savePlanting(false); }}>
          <label>Kultura<select value={form.crop_id} onChange={changeCrop} required>{crops.map((crop) => <option key={crop.id} value={crop.id}>{crop.name}</option>)}</select></label>
          <label>Sorta<select value={form.variety_id} onChange={(event) => { setForm({ ...form, variety_id: event.target.value }); clearSuggestions(); }} required>{(selectedCrop?.varieties || []).map((variety) => <option key={variety.id} value={variety.id}>{variety.name} · {maturityDaysForDate(variety, form.sowing_date)} dni ({maturitySeasonForDate(form.sowing_date).label})</option>)}</select></label>
          <label>Datum setve<input type="date" value={form.sowing_date} onChange={(event) => { setForm({ ...form, sowing_date: event.target.value }); clearSuggestions(); }} required /></label>
          <label>Gredica<select value={form.bed_id} onChange={(event) => { setForm({ ...form, bed_id: event.target.value }); setRotationWarning(null); }} required>{beds.map((bed) => <option key={bed.id} value={bed.id}>{bed.name} · {bed.status === "empty" ? "prazna" : "zasedena"} · {bed.area_m2} m²</option>)}</select></label>
          <div className="planting-actions"><button className="secondary-button" type="button" onClick={requestSuggestions} disabled={suggestionsLoading}>{suggestionsLoading ? "RAČUNAM PREDLOG ..." : "PAMETNI PREDLOG"}</button><button className="primary-button" type="submit">DODAJ SETEV</button></div>
        </form>
        {rotationWarning && <div className="rotation-warning"><strong>Opozorilo kolobarja</strong><p>{rotationWarning.message}</p><p>{rotationWarning.warnings?.[0]}</p><div className="warning-actions"><button type="button" onClick={() => setRotationWarning(null)}>IZBERI DRUGO GREDICO</button><button type="button" className="danger-button" onClick={() => savePlanting(true)}>VSEENO POSEJ</button></div></div>}
      </section>
      {suggestions && <PlantingSuggestions suggestions={suggestions} applySuggestion={applySuggestion} />}
      <section className="panel"><div className="section-heading"><div><p className="eyebrow">Aktivni rastni cikli</p><h2>Setve</h2></div><span>{plantings.length} aktivnih</span></div>{plantings.length === 0 ? <p className="empty-state">Prva setev še ni dodana.</p> : <div className="planting-list">{plantings.map((planting) => <article key={planting.id}><strong>{planting.bed} · {planting.crop} {planting.variety}</strong><span>{planting.sowing_date} → {planting.expected_harvest_date}</span>{planting.rotation_override && <small>Kolobar je uporabnik zavestno preglasil.</small>}</article>)}</div>}</section>
    </>
  );
}

function PlantingSuggestions({ suggestions, applySuggestion }) {
  const SuggestionCard = ({ item, showCrop = false }) => <article className={`advisor-card ${item.rating}`}>
    <div className="advisor-card-head"><div><span>Gredica {item.bed} · {item.area_m2} m²</span><strong>{showCrop ? `${item.crop} ${item.variety}` : `${suggestions.selected_crop} ${suggestions.selected_variety}`}</strong></div><span className={`advisor-rating ${item.rating}`}>{item.rating_label}</span></div>
    <div className="advisor-dates"><span>Setev {item.sowing_date}</span><span>Žetev okoli {item.expected_harvest_date}</span></div>
    {item.recent_history.length > 0 && <small className="advisor-history">Zadnji cikli: {item.recent_history.map((entry) => entry.crop).join(" → ")}</small>}
    <ul>{item.reasons.slice(0, 3).map((reason) => <li key={reason}>{reason}</li>)}</ul>
    {item.warnings.length > 0 && <div className="advisor-warnings">{item.warnings.map((warning) => <span key={warning}>⚠ {warning}</span>)}</div>}
    <button type="button" className="secondary-button" onClick={() => applySuggestion(item)}>UPORABI PREDLOG</button>
  </article>;
  return <section className="panel advisor-panel">
    <div className="section-heading"><div><p className="eyebrow">Kolobar in zgodovina</p><h2>Pametni predlog zasaditve</h2><p className="muted">Pregledani so zadnji štirje cikli, termin setve in že načrtovane zasedenosti.</p></div><span>{suggestions.empty_beds} praznih gredic</span></div>
    <div className="advisor-section"><h3>Najboljše gredice za {suggestions.selected_crop}</h3><div className="advisor-grid">{suggestions.recommended_beds.slice(0, 3).map((item) => <SuggestionCard key={`bed-${item.bed_id}`} item={item} />)}</div>{suggestions.recommended_beds.length === 0 && <p className="empty-state">Trenutno ni proste gredice za predlog.</p>}</div>
    <div className="advisor-section"><h3>Predlog kulture za vsako prazno gredico</h3><div className="advisor-grid">{suggestions.planting_ideas.map((item) => <SuggestionCard key={`idea-${item.bed_id}`} item={item} showCrop />)}</div></div>
    <p className="advisor-note">{suggestions.note}</p>
  </section>;
}

function TasksView({ tasks, beds, workers, taskDate, setTaskDate, taskForm, setTaskForm, createTask, completionTaskId, setCompletionTaskId, completion, setCompletion, completeTask }) {
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
                  <label>Trajanje (min)<input type="number" min={completion.worker_id ? "1" : "0"} value={completion.duration_minutes} onChange={(event) => setCompletion({ ...completion, duration_minutes: event.target.value })} required={Boolean(completion.worker_id)} /></label>
                  <label>Izvajalec<select value={completion.worker_id} onChange={(event) => setCompletion({ ...completion, worker_id: event.target.value })}><option value="">Brez obračuna dela</option>{workers.filter((worker) => worker.active).map((worker) => <option key={worker.id} value={worker.id}>{worker.name} · {worker.hourly_rate_eur.toFixed(2)} €/h</option>)}</select></label>
                  <label>Poraba<input type="number" min="0" step="0.01" value={completion.quantity_used} onChange={(event) => setCompletion({ ...completion, quantity_used: event.target.value })} /></label>
                  <label>Enota<input value={completion.unit} onChange={(event) => setCompletion({ ...completion, unit: event.target.value })} placeholder="L, kg, kos" /></label>
                  <label className="wide">Opomba<input value={completion.notes} onChange={(event) => setCompletion({ ...completion, notes: event.target.value })} placeholder="Kaj je bilo narejeno?" /></label>
                  <div className="completion-actions"><button type="button" className="text-button" onClick={() => setCompletionTaskId(null)}>PREKLIČI</button><button className="primary-button" type="submit">POTRDI OPRAVLJENO</button></div>
                </form>
              )}
              {task.status === "completed" && <div className="completion-summary">{task.duration_minutes != null && <span>{task.duration_minutes} min</span>}{task.labor_worker && <span>{task.labor_worker} · {task.labor_cost_eur.toFixed(2)} € dela</span>}{task.quantity_used != null && <span>{task.quantity_used} {task.unit || ""}</span>}{task.notes && <span>{task.notes}</span>}</div>}
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

function LaborView({ workers, beds, plantings, data, start, setStart, end, setEnd, workerForm, setWorkerForm, createWorker, laborForm, setLaborForm, createLaborEntry }) {
  const summary = data.summary || {};
  const selectedBed = beds.find((item) => String(item.id) === String(laborForm.bed_id));
  const matchingPlantings = plantings.filter((item) => !selectedBed || item.bed === selectedBed.name);
  const money = (amount) => `${(amount || 0).toFixed(2)} €`;
  return <>
    <section className="metric-grid labor-metrics">
      <article className="metric-card"><span>Delovne ure</span><strong>{(summary.hours || 0).toFixed(2)} h</strong><small>{summary.entry_count || 0} evidenc dela</small></article>
      <article className="metric-card"><span>Strošek dela</span><strong>{money(summary.cost_eur)}</strong><small>po shranjenih urnih postavkah</small></article>
      <article className="metric-card"><span>Brez gredice</span><strong className={summary.unallocated_hours ? "negative" : "positive"}>{(summary.unallocated_hours || 0).toFixed(2)} h</strong><small>{money(summary.unallocated_cost_eur)} še ni razporejeno</small></article>
    </section>
    <section className="labor-entry-grid">
      <form className="panel compact-form worker-form" onSubmit={createWorker}>
        <div className="section-heading"><div><p className="eyebrow">Ekipa in lastno delo</p><h2>Nov izvajalec</h2><p className="muted">Urna postavka je lahko tudi vrednost lastnega ali družinskega dela.</p></div></div>
        <label>Ime<input value={workerForm.name} onChange={(e) => setWorkerForm({ ...workerForm, name: e.target.value })} required /></label>
        <label>Vloga<input value={workerForm.role} onChange={(e) => setWorkerForm({ ...workerForm, role: e.target.value })} placeholder="Npr. pridelava" /></label>
        <label>Urna postavka (€)<input type="number" min="0" step="0.01" value={workerForm.hourly_rate_eur} onChange={(e) => setWorkerForm({ ...workerForm, hourly_rate_eur: e.target.value })} required /></label>
        <button className="secondary-button">DODAJ IZVAJALCA</button>
        <div className="worker-list">{workers.map((worker) => <span key={worker.id}><strong>{worker.name}</strong>{worker.role || "Brez vloge"} · {worker.hourly_rate_eur.toFixed(2)} €/h</span>)}{workers.length === 0 && <p className="empty-state">Izvajalec še ni dodan.</p>}</div>
      </form>
      <form className="panel labor-entry-form" onSubmit={createLaborEntry}>
        <div className="section-heading"><div><p className="eyebrow">Delo brez opravila</p><h2>Ročni vnos delovnih ur</h2><p className="muted">Za zaključena dnevna opravila se ure knjižijo že v obrazcu Opravila.</p></div></div>
        <label>Izvajalec<select value={laborForm.worker_id} onChange={(e) => setLaborForm({ ...laborForm, worker_id: e.target.value })} required><option value="">Izberi</option>{workers.filter((worker) => worker.active).map((worker) => <option key={worker.id} value={worker.id}>{worker.name} · {worker.hourly_rate_eur.toFixed(2)} €/h</option>)}</select></label>
        <label>Gredica<select value={laborForm.bed_id} onChange={(e) => setLaborForm({ ...laborForm, bed_id: e.target.value, planting_id: "" })}><option value="">Splošno / brez gredice</option>{beds.map((bed) => <option key={bed.id} value={bed.id}>{bed.name}</option>)}</select></label>
        <label>Setev (neobvezno)<select value={laborForm.planting_id} onChange={(e) => setLaborForm({ ...laborForm, planting_id: e.target.value })}><option value="">Brez setve</option>{matchingPlantings.map((item) => <option key={item.id} value={item.id}>{item.crop} {item.variety}</option>)}</select></label>
        <label>Datum<input type="date" value={laborForm.work_date} onChange={(e) => setLaborForm({ ...laborForm, work_date: e.target.value })} required /></label>
        <label>Trajanje (min)<input type="number" min="1" max="1440" value={laborForm.duration_minutes} onChange={(e) => setLaborForm({ ...laborForm, duration_minutes: e.target.value })} required /></label>
        <label>Druga urna postavka (€)<input type="number" min="0" step="0.01" value={laborForm.hourly_rate_eur} onChange={(e) => setLaborForm({ ...laborForm, hourly_rate_eur: e.target.value })} placeholder="Privzeta izvajalčeva" /></label>
        <label className="wide">Opis<input value={laborForm.description} onChange={(e) => setLaborForm({ ...laborForm, description: e.target.value })} placeholder="Npr. priprava gredice in zastirka" required /></label>
        <button className="primary-button" disabled={!workers.length}>SHRANI DELO</button>
      </form>
    </section>
    <section className="panel labor-report-panel">
      <div className="section-heading"><div><p className="eyebrow">Obdobje in razporeditev</p><h2>Poročilo o delu</h2></div><div className="labor-range"><label>Od<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label><label>Do<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label></div></div>
      <div className="labor-breakdown-grid">
        <div><h3>Po izvajalcih</h3>{data.by_worker.length === 0 ? <p className="empty-state">V obdobju ni dela.</p> : data.by_worker.map((row) => <article key={row.worker_id}><div><strong>{row.worker}</strong><span>{row.entry_count} evidenc</span></div><div><strong>{row.hours.toFixed(2)} h</strong><span>{money(row.cost_eur)}</span></div></article>)}</div>
        <div><h3>Po gredicah</h3>{data.by_bed.length === 0 ? <p className="empty-state">Delo še ni razporejeno na gredice.</p> : data.by_bed.map((row) => <article key={row.bed_id}><div><strong>Gredica {row.bed}</strong><span>{row.entry_count} evidenc</span></div><div><strong>{row.hours.toFixed(2)} h</strong><span>{money(row.cost_eur)}</span></div></article>)}</div>
      </div>
      <p className="labor-note">{data.note}</p>
    </section>
    <section className="panel">
      <div className="section-heading"><div><p className="eyebrow">Dnevnik</p><h2>Evidentirano delo</h2></div><span>{data.entries.length} zapisov</span></div>
      {data.entries.length === 0 ? <p className="empty-state">Za izbrano obdobje ni evidenc.</p> : <div className="labor-history">{data.entries.map((entry) => <article key={entry.id}><time>{entry.work_date}</time><div><strong>{entry.description}</strong><span>{entry.worker}{entry.bed ? ` · gredica ${entry.bed}` : " · brez gredice"}{entry.task_id ? " · iz opravila" : ""}</span></div><div><strong>{entry.hours.toFixed(2)} h</strong><span>{money(entry.total_cost_eur)}</span></div></article>)}</div>}
    </section>
  </>;
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
        <label>Kategorija<select value={costForm.category} onChange={(e) => setCostForm({ ...costForm, category: e.target.value })}><option value="labor">Delo – ročni strošek</option><option value="seed">Seme</option><option value="fertilizer">Gnojilo</option><option value="water">Voda</option><option value="packaging">Embalaža</option><option value="other">Drugo</option></select></label>
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
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Rezultat na površino</p><h2>Dobiček po gredicah</h2><p className="muted">Čas iz modula Delo se obračuna samodejno; istega dela ne vnesi še enkrat kot ročni strošek.</p></div></div><div className="economics-table"><strong>Gredica</strong><strong>Žetev</strong><strong>Stroški</strong><strong>Prihodki</strong><strong>Dobiček</strong>{economics.map((item) => <React.Fragment key={item.bed_id}><span>{item.bed}</span><span>{item.harvested_kg} kg</span><span className="economics-cost">{item.costs_eur.toFixed(2)} €<small>{item.material_costs_eur.toFixed(2)} € material</small><small>{item.labor_costs_eur.toFixed(2)} € delo</small></span><span>{item.revenue_eur.toFixed(2)} €</span><strong className={item.profit_eur >= 0 ? "positive" : "negative"}>{item.profit_eur.toFixed(2)} €</strong></React.Fragment>)}</div></section>
  </>;
}

function ProfitabilityTable({ rows, nameKey }) {
  const money = (value) => `${Number(value || 0).toFixed(2)} €`;
  const ratio = (value, suffix) => value == null ? "—" : `${Number(value).toFixed(2)} ${suffix}`;
  if (rows.length === 0) return <p className="empty-state">V izbranem obdobju ni podatkov.</p>;
  return <div className="profitability-table">
    <b>Naziv</b><b>Površina</b><b>Žetev</b><b>Prodano</b><b>Neto prihodek</b><b>Stroški</b><b>Dobiček</b><b>Marža</b><b>Na m²</b>
    {rows.map((row) => <React.Fragment key={`${nameKey}-${row[`${nameKey}_id`]}`}>
      <span><strong>{row[nameKey]}</strong>{row.crops?.length > 0 && <small>{row.crops.join(", ")}</small>}</span>
      <span>{row.area_m2.toFixed(2)} m²</span>
      <span>{row.harvested_kg.toFixed(2)} kg<small>{ratio(row.harvest_kg_m2, "kg/m²")}</small></span>
      <span>{row.sold_kg.toFixed(2)} kg</span>
      <span>{money(row.net_revenue_eur)}<small>bruto {money(row.gross_revenue_eur)} · dobropisi {money(row.credit_notes_eur)}</small></span>
      <span>{money(row.costs_eur)}<small>{money(row.direct_costs_eur)} neposredno · {money(row.material_costs_eur)} material · {money(row.labor_costs_eur)} delo</small></span>
      <strong className={row.profit_eur >= 0 ? "positive" : "negative"}>{money(row.profit_eur)}<small>{ratio(row.profit_eur_per_labor_hour, "€/h")}</small></strong>
      <span>{ratio(row.margin_pct, "%")}</span>
      <span>{ratio(row.profit_eur_m2, "€/m²")}<small>prihodek {ratio(row.revenue_eur_m2, "€/m²")}</small></span>
    </React.Fragment>)}
  </div>;
}

function ProfitabilityView({ data, start, setStart, end, setEnd }) {
  const summary = data.summary || {};
  const money = (value) => `${Number(value || 0).toFixed(2)} €`;
  const ratio = (value, suffix) => value == null ? "—" : `${Number(value).toFixed(2)} ${suffix}`;
  return <>
    <section className="panel report-heading">
      <div><p className="eyebrow">Sezonski rezultat</p><h2>Dobičkonosnost pridelave</h2><p className="muted">{data.note}</p></div>
      <div className="report-controls"><label>Od<input type="date" value={start} onChange={(e) => { const value = e.target.value; setStart(value); if (end < value) setEnd(value); }} /></label><label>Do<input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} /></label><ProtectedDownloadButton className="secondary-button export-button" path={`/api/profitability-report/export.csv?start=${start}&end=${end}`} filename={`donosnost-${start}-${end}.csv`}>IZVOZI CSV</ProtectedDownloadButton></div>
    </section>
    <section className="metric-grid profitability-metrics">
      <article className="metric-card"><span>Dobiček</span><strong className={Number(summary.profit_eur || 0) >= 0 ? "positive" : "negative"}>{money(summary.profit_eur)}</strong><small>marža {ratio(summary.margin_pct, "%")}</small></article>
      <article className="metric-card"><span>Neto prihodki</span><strong>{money(summary.net_revenue_eur)}</strong><small>bruto {money(summary.gross_revenue_eur)} · dobropisi {money(summary.credit_notes_eur)}</small></article>
      <article className="metric-card"><span>Skupni stroški</span><strong>{money(summary.costs_eur)}</strong><small>{money(summary.direct_costs_eur)} neposredno · {money(summary.material_costs_eur)} material · {money(summary.labor_costs_eur)} delo · {money(summary.overhead_costs_eur)} splošno</small></article>
      <article className="metric-card"><span>Žetev</span><strong>{Number(summary.harvested_kg || 0).toFixed(2)} kg</strong><small>{Number(summary.sold_kg || 0).toFixed(2)} kg prodano · {ratio(summary.harvest_kg_m2, "kg/m²")}</small></article>
      <article className="metric-card"><span>Rezultat na površino</span><strong>{ratio(summary.profit_eur_m2, "€/m²")}</strong><small>{Number(summary.active_area_m2 || 0).toFixed(2)} m² aktivnih · prihodek {ratio(summary.revenue_eur_m2, "€/m²")}</small></article>
      <article className="metric-card"><span>Učinek dela</span><strong>{ratio(summary.profit_eur_per_labor_hour, "€/h")}</strong><small>{Number(summary.labor_hours || 0).toFixed(2)} ur evidentiranega dela</small></article>
    </section>
    {Number(summary.unallocated_costs_eur || 0) > 0 && <aside className="allocation-note"><strong>{money(summary.unallocated_costs_eur)} stroškov ni pripisanih setvi.</strong><span>V skupnem rezultatu so vključeni, pri kulturah pa ne; pri gredicah se pokažejo, kadar je bila gredica izbrana. Od tega {money(summary.unallocated_direct_costs_eur)} neposrednih, {money(summary.unallocated_material_costs_eur)} materiala, {money(summary.unallocated_labor_costs_eur)} dela in {money(summary.unallocated_overhead_costs_eur)} splošnih stroškov kmetije.</span></aside>}
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Po površinah</p><h2>Rezultat po gredicah</h2></div><span>{data.by_bed.length} aktivnih</span></div><ProfitabilityTable rows={data.by_bed} nameKey="bed" /></section>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Po pridelkih</p><h2>Rezultat po kulturah</h2><p className="muted">Površina iste setve se pri kulturi upošteva samo enkrat, tudi če ima več žetev ali prodaj.</p></div><span>{data.by_crop.length} kultur</span></div><ProfitabilityTable rows={data.by_crop} nameKey="crop" /></section>
  </>;
}

function FarmExpensesView({ expenses, form, setForm, createExpense, start, setStart, end, setEnd }) {
  const categoryLabels = { fuel: "Gorivo", utilities: "Elektrika in voda", rent: "Najemnina", insurance: "Zavarovanje", maintenance: "Vzdrževanje", administration: "Administracija", other: "Drugo" };
  const methodLabels = { cash: "Gotovina", card: "Kartica", bank_transfer: "Nakazilo" };
  const total = expenses.reduce((sum, item) => sum + item.amount_eur, 0);
  const byMethod = (method) => expenses.filter((item) => item.payment_method === method).reduce((sum, item) => sum + item.amount_eur, 0);
  return <>
    <section className="panel report-heading">
      <div><p className="eyebrow">Stroški celotne kmetije</p><h2>Splošni stroški</h2><p className="muted">Sem vnesi gorivo, elektriko, najemnino, zavarovanje in podobne stroške, ki ne pripadajo eni gredici. Nabavljenega materiala ali stroška določene gredice tu ne vnašaj še enkrat.</p></div>
      <div className="report-controls"><label>Od<input type="date" value={start} onChange={(e) => { const value = e.target.value; setStart(value); if (end < value) setEnd(value); }} /></label><label>Do<input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} /></label></div>
    </section>
    <section className="metric-grid farm-expense-metrics">
      <article className="metric-card"><span>Skupaj</span><strong>{total.toFixed(2)} €</strong><small>{expenses.length} evidentiranih stroškov</small></article>
      <article className="metric-card"><span>Gotovina</span><strong>{byMethod("cash").toFixed(2)} €</strong><small>zmanjša pričakovano gotovino ob zaključku dneva</small></article>
      <article className="metric-card"><span>Kartica in nakazila</span><strong>{(byMethod("card") + byMethod("bank_transfer")).toFixed(2)} €</strong><small>kartica {byMethod("card").toFixed(2)} € · nakazila {byMethod("bank_transfer").toFixed(2)} €</small></article>
    </section>
    <section className="farm-expense-grid">
      <form className="panel farm-expense-form" onSubmit={createExpense}>
        <div className="section-heading"><div><p className="eyebrow">Nov odliv</p><h2>Dodaj splošni strošek</h2></div></div>
        <div className="farm-expense-fields">
          <label>Datum<input type="date" value={form.expense_date} onChange={(e) => setForm({ ...form, expense_date: e.target.value })} required /></label>
          <label>Vrsta<select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{Object.entries(categoryLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>Znesek (€)<input type="number" min="0.01" step="0.01" value={form.amount_eur} onChange={(e) => setForm({ ...form, amount_eur: e.target.value })} required /></label>
          <label>Način plačila<select value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>{Object.entries(methodLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>Dobavitelj<input value={form.supplier} onChange={(e) => setForm({ ...form, supplier: e.target.value })} placeholder="Neobvezno" /></label>
          <label>Številka listine<input value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} placeholder="Npr. račun ali potrdilo" /></label>
          <label className="wide">Opis<input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Kaj je bilo plačano?" required /></label>
        </div>
        <button className="primary-button">SHRANI STROŠEK</button>
      </form>
      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">Izbrano obdobje</p><h2>Zgodovina stroškov</h2></div><span>{expenses.length} zapisov</span></div>
        {expenses.length === 0 ? <p className="empty-state">V izbranem obdobju ni splošnih stroškov.</p> : <div className="farm-expense-list">{expenses.map((item) => <article key={item.id}><div><strong>{item.description}</strong><span>{item.expense_date} · {categoryLabels[item.category] || item.category} · {methodLabels[item.payment_method] || item.payment_method}</span>{(item.supplier || item.reference) && <small>{item.supplier || "Brez dobavitelja"}{item.reference ? ` · ${item.reference}` : ""}</small>}</div><strong>{item.amount_eur.toFixed(2)} €</strong></article>)}</div>}
      </section>
    </section>
  </>;
}

function OrdersView({ inventory, crops, customers, orders, customerForm, setCustomerForm, createCustomer, orderForm, setOrderForm, createOrder, changeOrderStatus, openOrderDocument, issueInvoice, openInvoicePdf, document, setDocument, retailSales, quickSaleForm, setQuickSaleForm, quickSaleCart, addQuickSaleItem, changeQuickSaleHarvest, removeQuickSaleItem, createQuickSale, openRetailDocument, priceList, priceForm, setPriceForm, saveProductPrice, salesSettings, setSalesSettings, saveSalesSettings }) {
  const available = inventory.filter((item) => item.available_kg > 0);
  const cartTotal = quickSaleCart.reduce((sum, item) => sum + item.line_total_eur, 0);
  return <>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Prodajna zaloga</p><h2>Na voljo</h2></div><span>{available.reduce((sum, item) => sum + item.available_kg, 0).toFixed(1)} kg</span></div>
      <div className="inventory-grid">{inventory.map((item) => <article key={item.harvest_id}><strong>{item.crop} {item.variety}</strong><span>Gredica {item.bed} · kakovost {item.quality}</span><div><b>{item.available_kg} kg na voljo</b><small>{item.reserved_kg} kg rezervirano · {item.sold_kg} kg prodano</small></div></article>)}</div>
    </section>
    <section className="quick-sale-grid">
      <div className="panel quick-sale-form"><div><p className="eyebrow">Tržnica in prodaja na domu</p><h2>Košarica hitre prodaje</h2><span className="exemption-note">Več pridelkov v eni prodaji · končni potrošnik je privzet</span></div>
        <label>Kupec<select value={quickSaleForm.customer_id} onChange={(e) => setQuickSaleForm({ ...quickSaleForm, customer_id: e.target.value })}><option value="">Končni potrošnik (brez osebnih podatkov)</option>{customers.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.customer_type === "business" ? "poslovni" : "končni"}</option>)}</select></label>
        <label>Datum<input type="date" value={quickSaleForm.sale_date} onChange={(e) => setQuickSaleForm({ ...quickSaleForm, sale_date: e.target.value })} required /></label>
        <label>Plačilo<select value={quickSaleForm.payment_method} onChange={(e) => setQuickSaleForm({ ...quickSaleForm, payment_method: e.target.value })}><option value="cash">Gotovina</option><option value="card">Kartica</option><option value="bank_transfer">Nakazilo</option></select></label>
        <form className="quick-sale-line-form" onSubmit={addQuickSaleItem}>
          <label>Artikel<select value={quickSaleForm.harvest_id} onChange={changeQuickSaleHarvest} required>{available.map((item) => <option key={item.harvest_id} value={item.harvest_id}>{item.crop} {item.variety} · kakovost {item.quality} · {item.available_kg} kg{item.suggested_price_per_kg_eur ? ` · ${item.suggested_price_per_kg_eur.toFixed(2)} €/kg` : ""}</option>)}</select></label>
          <label>Količina (kg)<input type="number" min="0.01" step="0.01" value={quickSaleForm.quantity_kg} onChange={(e) => setQuickSaleForm({ ...quickSaleForm, quantity_kg: e.target.value })} required /></label>
          <label>Cena/kg (€)<input type="number" min="0.01" step="0.01" value={quickSaleForm.price_per_kg_eur} onChange={(e) => setQuickSaleForm({ ...quickSaleForm, price_per_kg_eur: e.target.value })} required /></label>
          <button className="secondary-button">DODAJ V KOŠARICO</button>
        </form>
        <div className="quick-sale-cart">{quickSaleCart.length === 0 ? <p className="empty-state">Košarica je prazna.</p> : quickSaleCart.map((item) => <article key={item.harvest_id}><div><strong>{item.crop} {item.variety}</strong><span>Gredica {item.bed} · kakovost {item.quality} · {item.quantity_kg.toFixed(2)} kg × {item.price_per_kg_eur.toFixed(2)} €</span></div><strong>{item.line_total_eur.toFixed(2)} €</strong><button className="icon-button" type="button" onClick={() => removeQuickSaleItem(item.harvest_id)}>✕</button></article>)}</div>
        <div className="quick-sale-checkout"><span>Skupaj</span><strong>{cartTotal.toFixed(2)} €</strong><button className="primary-button" type="button" disabled={!quickSaleCart.length} onClick={createQuickSale}>ZABELEŽI PRODAJO</button></div>
      </div>
      {salesSettings && <form className="panel compact-form" onSubmit={saveSalesSettings}><h2>Nastavitve prodaje</h2><label className="check-label"><input type="checkbox" checked={salesSettings.basic_agriculture_invoice_exemption} onChange={(e) => setSalesSettings({ ...salesSettings, basic_agriculture_invoice_exemption: e.target.checked })} /> Izjema osnovne kmetijske dejavnosti po 81.a</label><label>Naziv kmetije<input value={salesSettings.seller_name} onChange={(e) => setSalesSettings({ ...salesSettings, seller_name: e.target.value })} required /></label><label>Davčna številka<input value={salesSettings.seller_tax_number || ""} onChange={(e) => setSalesSettings({ ...salesSettings, seller_tax_number: e.target.value || null })} /></label><button className="secondary-button">SHRANI NASTAVITVE</button></form>}
    </section>
    <form className="panel price-list-form" onSubmit={saveProductPrice}><div className="section-heading"><div><p className="eyebrow">Privzete cene</p><h2>Cenik po kakovosti</h2><p className="muted">Cena se samodejno predlaga v košarici, posamezno prodajo pa jo lahko še vedno spremeniš.</p></div><button className="secondary-button">SHRANI CENO</button></div><label>Kultura<select value={priceForm.crop_id} onChange={(e) => setPriceForm({ ...priceForm, crop_id: e.target.value })} required>{crops.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Kakovost<select value={priceForm.quality} onChange={(e) => setPriceForm({ ...priceForm, quality: e.target.value })}><option value="A">A – prva</option><option value="B">B – druga</option></select></label><label>Cena/kg (€)<input type="number" min="0.01" step="0.01" value={priceForm.price_per_kg_eur} onChange={(e) => setPriceForm({ ...priceForm, price_per_kg_eur: e.target.value })} required /></label><div className="price-list-chips">{priceList.map((item) => <span key={item.id}><strong>{item.crop} · {item.quality}</strong>{item.price_per_kg_eur.toFixed(2)} €/kg</span>)}{priceList.length === 0 && <p className="empty-state">Cenik še nima vnosov.</p>}</div></form>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Neposredna prodaja</p><h2>Zadnje hitre prodaje</h2></div><span>{retailSales.length} zapisov</span></div><div className="retail-sales-list">{retailSales.map((sale) => <article key={sale.id}><div><strong>{sale.number} · {sale.customer}</strong><span>{sale.sale_date} · {sale.total_eur.toFixed(2)} € · {sale.payment_method === "cash" ? "gotovina" : sale.payment_method === "card" ? "kartica" : "nakazilo"}</span></div><div className="order-actions"><button className="text-button" onClick={() => openRetailDocument(sale.id, "receipt")}>POTRDILO</button>{sale.invoice_required && !sale.invoice && <button className="secondary-button" onClick={() => issueInvoice("retail_sale", sale.id)}>IZDAJ RAČUN</button>}{sale.invoice && sale.invoice.fiscal_status !== "pending" && <button className="secondary-button" onClick={() => openInvoicePdf(sale.invoice.id)}>PDF RAČUNA</button>}{sale.invoice?.fiscal_status === "pending" && <span className="fiscal-badge pending">MANJKA EOR</span>}</div></article>)}</div></section>
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
        <div className="order-actions"><button className="text-button" onClick={() => openOrderDocument(order.id, "delivery_note")}>DOBAVNICA</button>{order.status === "fulfilled" && order.customer_type === "business" && !order.invoice && <button className="secondary-button" onClick={() => issueInvoice("order", order.id)}>IZDAJ RAČUN</button>}{order.invoice && order.invoice.fiscal_status !== "pending" && <button className="text-button" onClick={() => openInvoicePdf(order.invoice.id)}>PDF RAČUNA</button>}{order.invoice?.fiscal_status === "pending" && <span className="fiscal-badge pending">MANJKA EOR</span>}{order.status === "confirmed" && <><button className="secondary-button" onClick={() => changeOrderStatus(order.id, "fulfilled")}>DOSTAVLJENO</button><button className="text-button danger-text" onClick={() => changeOrderStatus(order.id, "cancelled")}>PREKLIČI</button></>}</div>
      </article>)}</div>
    </section>
    {document && (() => { const record = document.order || document.sale; const customer = document.customer || { name: record.customer, address: "" }; return <section className="panel printable-document"><div className="section-heading"><div><p className="eyebrow">{document.document_type === "invoice" ? "Račun" : document.document_type === "delivery_note" ? "Dobavnica" : "Interno potrdilo prodaje"}</p><h2>{document.document_number}</h2></div><div className="order-actions"><button className="secondary-button" onClick={() => window.print()}>NATISNI</button><button className="icon-button" onClick={() => setDocument(null)}>✕</button></div></div>{document.seller && <p><strong>{document.seller.name}</strong><br />{document.seller.tax_number || ""}</p>}<p><strong>Kupec:</strong> {customer.name}<br />{customer.address || ""}</p><div className="document-lines">{record.items.map((item) => <div key={item.id}><span>{item.crop} {item.variety} · {item.quantity_kg} kg</span><strong>{item.line_total_eur.toFixed(2)} €</strong></div>)}</div><div className="document-total">Skupaj <strong>{record.total_eur.toFixed(2)} €</strong></div>{document.fiscal_confirmation_required && <p className="forecast-warning">Ta račun je treba pred uporabo vključiti v ustrezen postopek davčnega potrjevanja.</p>}</section>; })()}
  </>;
}

function InvoicesView({ invoices, profile, setProfile, saveProfile, openPdf, confirmFiscal, issueCreditNote, recordRefund }) {
  const paymentLabel = (value) => ({ bank_transfer: "Nakazilo", cash: "Gotovina", card: "Kartica" }[value] || value);
  const fiscalLabel = (value) => ({ not_required: "EOR ni potreben", pending: "Čaka EOR", confirmed: "Davčno potrjeno" }[value] || value);
  return <>
    {profile && <form className="panel invoice-profile-form" onSubmit={saveProfile}>
      <div className="section-heading"><div><p className="eyebrow">Glava dokumenta</p><h2>Podatki za račune</h2><p className="muted">Naziv in davčna številka se urejata v nastavitvah prodaje. Ti podatki se ob izdaji zamrznejo.</p></div><button className="secondary-button">SHRANI</button></div>
      <label>Naslov prodajalca<textarea value={profile.seller_address || ""} onChange={(e) => setProfile({ ...profile, seller_address: e.target.value })} required /></label>
      <label>IBAN<input value={profile.seller_iban || ""} onChange={(e) => setProfile({ ...profile, seller_iban: e.target.value || null })} /></label>
      <label>Matična številka<input value={profile.seller_registration_number || ""} onChange={(e) => setProfile({ ...profile, seller_registration_number: e.target.value || null })} /></label>
      <label>Davčna opomba<input value={profile.vat_note || ""} onChange={(e) => setProfile({ ...profile, vat_note: e.target.value || null })} placeholder="Npr. klavzula glede DDV" /></label>
      <label>Poslovni prostor<input value={profile.business_premise_code} onChange={(e) => setProfile({ ...profile, business_premise_code: e.target.value })} required /></label>
      <label>Naprava<input value={profile.device_code} onChange={(e) => setProfile({ ...profile, device_code: e.target.value })} required /></label>
      <label>Privzeti rok (dni)<input type="number" min="0" max="365" value={profile.default_due_days} onChange={(e) => setProfile({ ...profile, default_due_days: Number(e.target.value) })} required /></label>
    </form>}
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Nespremenljivi arhiv</p><h2>Izdani računi in dobropisi</h2></div><span>{invoices.length} računov</span></div>
      <p className="invoice-legal-note">Končni PDF za gotovino ali kartico je odklenjen šele po vpisu EOR. GrowMaster EOR shrani, davčne potrditve pa brez vašega certifikata ne izvaja sam.</p>
      {invoices.length === 0 ? <p className="empty-state">Račun še ni izdan. Izdate ga pri dostavljenem poslovnem naročilu ali poslovni hitri prodaji.</p> : <div className="invoice-list">{invoices.map((invoice) => <article key={invoice.id} className={invoice.status}>
        <div className="invoice-main"><div><span className={`fiscal-badge ${invoice.fiscal_status}`}>{fiscalLabel(invoice.fiscal_status)}</span><strong>{invoice.number} · {invoice.customer.name}</strong><span>Izdano {invoice.issued_on} · dobava {invoice.supply_date} · rok {invoice.due_date}</span><span>{paymentLabel(invoice.payment_method)} · {invoice.source_type === "order" ? "naročilo" : "hitra prodaja"} #{invoice.source_id}</span></div><div><strong>{invoice.total_eur.toFixed(2)} €</strong><span>{invoice.status === "credited" ? "Dobropisano" : `${invoice.outstanding_eur.toFixed(2)} € odprto`}</span></div></div>
        <div className="order-actions">{invoice.fiscal_status === "pending" && <button className="secondary-button" onClick={() => confirmFiscal(invoice.id)}>VPIŠI EOR</button>}{invoice.fiscal_status !== "pending" && <button className="secondary-button" onClick={() => openPdf(invoice.id)}>ODPRI PDF</button>}{invoice.status !== "credited" && <button className="text-button danger-text" onClick={() => issueCreditNote(invoice.id)}>IZDAJ DOBROPIS</button>}</div>
        {invoice.credit_note && <div className="credit-note-row"><div className="credit-note-details"><strong>{invoice.credit_note.number}</strong><span>{invoice.credit_note.issued_on} · {invoice.credit_note.reason}</span><span>Vrnjeno {invoice.credit_note.refunded_eur.toFixed(2)} € · še vračljivo {invoice.credit_note.refundable_eur.toFixed(2)} €</span>{invoice.credit_note.refunds.length > 0 && <div className="refund-history">{invoice.credit_note.refunds.map((refund) => <span key={refund.id}>{refund.refund_date} · {refund.amount_eur.toFixed(2)} € · {paymentLabel(refund.payment_method)}{refund.notes ? ` · ${refund.notes}` : ""}</span>)}</div>}</div><div className="order-actions">{invoice.credit_note.fiscal_status === "pending" ? <button className="secondary-button" onClick={() => confirmFiscal(invoice.id, invoice.credit_note.id)}>VPIŠI EOR DOBROPISA</button> : <><ProtectedDownloadButton path={`/api/credit-notes/${invoice.credit_note.id}/pdf`} filename={`dobropis-${invoice.credit_note.number}.pdf`} open>PDF DOBROPISA</ProtectedDownloadButton>{invoice.credit_note.refundable_eur > 0 && <button className="primary-button" onClick={() => recordRefund(invoice.credit_note, invoice)}>EVIDENTIRAJ VRAČILO</button>}</>}</div></div>}
      </article>)}</div>}
    </section>
  </>;
}

function SalesReportView({ report, start, setStart, end, setEnd }) {
  const summary = report.summary || {};
  const paymentLabel = (method) => ({ cash: "Gotovina", card: "Kartica", bank_transfer: "Nakazilo", invoice: "Izdani račun", unclassified: "Ni določeno" }[method] || method);
  return <>
    <section className="panel report-heading">
      <div><p className="eyebrow">Dnevni register</p><h2>Pregled prodaje</h2><p className="muted">{report.note}</p></div>
      <div className="report-controls"><label>Od<input type="date" value={start} onChange={(e) => { const value = e.target.value; setStart(value); if (end < value) setEnd(value); }} /></label><label>Do<input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} /></label><ProtectedDownloadButton className="secondary-button export-button" path={`/api/sales-report/export.csv?start=${start}&end=${end}`} filename={`prodaja-${start}-${end}.csv`}>IZVOZI CSV</ProtectedDownloadButton></div>
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

function CashFlowView({ data, start, setStart, end, setEnd }) {
  const summary = data.summary || {};
  const categoryLabels = { seed: "Seme", labor: "Delo", fertilizer: "Gnojila", water: "Voda", packaging: "Embalaža", purchasing: "Plačila dobaviteljem", fuel: "Gorivo", utilities: "Elektrika in voda", rent: "Najemnina", insurance: "Zavarovanje", maintenance: "Vzdrževanje", administration: "Administracija", other: "Drugo" };
  const methodLabels = { cash: "Gotovina", card: "Kartica", bank_transfer: "Nakazilo" };
  const sourceLabel = (source) => ({ retail_sale: "hitra prodaja", order_payment: "plačilo računa", cost: "strošek", farm_expense: "splošni strošek", refund: "vračilo kupcu", supplier_payment: "plačilo dobavitelju" }[source] || source);
  return <>
    <section className="panel report-heading"><div><p className="eyebrow">Dejanski premiki</p><h2>Denarni tok</h2><p className="muted">{data.note}</p></div><div className="report-controls"><label>Od<input type="date" value={start} onChange={(e) => { const value = e.target.value; setStart(value); if (end < value) setEnd(value); }} /></label><label>Do<input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} /></label><ProtectedDownloadButton className="secondary-button export-button" path={`/api/cash-flow/export.csv?start=${start}&end=${end}`} filename={`denarni-tok-${start}-${end}.csv`}>IZVOZI CSV</ProtectedDownloadButton></div></section>
    <section className="metric-grid cashflow-metrics">
      <article className="metric-card"><span>Prilivi</span><strong className="positive">{(summary.inflow_eur || 0).toFixed(2)} €</strong><small>{summary.inflow_count || 0} prejemkov</small></article>
      <article className="metric-card"><span>Odlivi</span><strong className="negative">{(summary.outflow_eur || 0).toFixed(2)} €</strong><small>{summary.outflow_count || 0} odlivov · vračila {(summary.refund_eur || 0).toFixed(2)} € · dobavitelji {(summary.supplier_payments_eur || 0).toFixed(2)} €</small></article>
      <article className="metric-card"><span>Neto tok</span><strong className={(summary.net_eur || 0) < 0 ? "negative" : "positive"}>{(summary.net_eur || 0).toFixed(2)} €</strong><small>prilivi minus odlivi</small></article>
      <article className="metric-card"><span>Načini priliva</span><strong>{(summary.bank_transfer_eur || 0).toFixed(2)} €</strong><small>nakazila · gotovina {(summary.cash_eur || 0).toFixed(2)} € · kartice {(summary.card_eur || 0).toFixed(2)} €</small></article>
    </section>
    <section className="cashflow-summary-grid">
      <div className="panel"><div className="section-heading"><div><p className="eyebrow">Po dnevih</p><h2>Dnevni tok</h2></div><span>{data.daily.length} dni</span></div>{data.daily.length === 0 ? <p className="empty-state">V obdobju ni evidentiranih denarnih premikov.</p> : <div className="cashflow-daily-list">{data.daily.map((day) => <article key={day.date}><time>{day.date}</time><span className="positive">+{day.inflow_eur.toFixed(2)} €</span><span className="negative">−{day.outflow_eur.toFixed(2)} €</span><strong className={day.net_eur < 0 ? "negative" : "positive"}>{day.net_eur.toFixed(2)} €</strong></article>)}</div>}</div>
      <div className="panel"><div className="section-heading"><div><p className="eyebrow">Odlivi</p><h2>Stroški po vrsti</h2></div></div>{Object.keys(summary.costs_by_category || {}).length === 0 ? <p className="empty-state">V obdobju ni evidentiranih stroškov.</p> : <div className="cost-category-list">{Object.entries(summary.costs_by_category).map(([category, amount]) => <article key={category}><span>{categoryLabels[category] || category}</span><strong>{amount.toFixed(2)} €</strong></article>)}</div>}</div>
    </section>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Premiki</p><h2>Denarni dnevnik</h2></div><span>{data.entries.length} zapisov</span></div><div className="cashflow-table"><b>Datum</b><b>Referenca</b><b>Opis</b><b>Način / vrsta</b><b>Priliv</b><b>Odliv</b>{data.entries.map((entry) => <React.Fragment key={entry.key}><span>{entry.date}</span><span>{entry.reference}<small>{sourceLabel(entry.source)}</small></span><span>{entry.description}<small>{entry.party}</small></span><span>{methodLabels[entry.method] || categoryLabels[entry.category] || entry.category}</span><strong className="positive">{entry.direction === "inflow" ? `${entry.amount_eur.toFixed(2)} €` : "—"}</strong><strong className="negative">{entry.direction === "outflow" ? `${entry.amount_eur.toFixed(2)} €` : "—"}</strong></React.Fragment>)}</div></section>
  </>;
}

function DayCloseView({ closes, preview, form, setForm, closeDay }) {
  const value = preview || {};
  const countedCash = Number(form.counted_cash_eur);
  const liveDifference = Number.isFinite(countedCash) && form.counted_cash_eur !== ""
    ? countedCash - (value.expected_cash_eur || 0)
    : null;
  const money = (amount) => `${(amount || 0).toFixed(2)} €`;
  return <>
    <section className="panel day-close-heading">
      <div><p className="eyebrow">Konec prodajnega dne</p><h2>Dnevni zaključek</h2><p className="muted">Seštevek prodaje, prejetih plačil, vračil, dobaviteljev in splošnih stroškov. Zaključek shrani nespremenljiv posnetek in zaklene nove denarne vnose za izbrani datum.</p></div>
      {value.closed && <span className="closed-day-badge">✓ DAN ZAKLJUČEN</span>}
    </section>
    <section className="metric-grid day-close-metrics">
      <article className="metric-card"><span>Prilivi</span><strong className="positive">{money(value.total_inflow_eur)}</strong><small>{value.retail_sale_count || 0} hitrih prodaj · {value.payment_count || 0} plačil računov</small></article>
      <article className="metric-card"><span>Odlivi</span><strong className="negative">{money(value.total_outflow_eur)}</strong><small>{value.refund_count || 0} vračil · {value.supplier_payment_count || 0} plačil dobaviteljem · {value.farm_expense_count || 0} splošnih stroškov</small></article>
      <article className="metric-card"><span>Pričakovana gotovina</span><strong>{money(value.expected_cash_eur)}</strong><small>začetna + prilivi − vsi gotovinski odlivi</small></article>
      <article className="metric-card"><span>Razlika v blagajni</span><strong className={(value.closed ? value.difference_eur : liveDifference) < 0 ? "negative" : "positive"}>{value.closed ? money(value.difference_eur) : liveDifference === null ? "—" : money(liveDifference)}</strong><small>prešteto minus pričakovano</small></article>
    </section>
    <section className="day-close-grid">
      <form className="panel day-close-form" onSubmit={closeDay}>
        <div className="section-heading"><div><p className="eyebrow">Blagajna</p><h2>{value.closed ? "Shranjeni zaključek" : "Preštej in zaključi"}</h2></div></div>
        <label>Poslovni datum<input type="date" value={form.business_date} onChange={(e) => setForm({ ...form, business_date: e.target.value, counted_cash_eur: "", notes: "" })} required /></label>
        <label>Začetna gotovina (€)<input type="number" min="0" step="0.01" value={value.closed ? value.opening_cash_eur : form.opening_cash_eur} onChange={(e) => setForm({ ...form, opening_cash_eur: e.target.value })} disabled={value.closed} required /></label>
        <label>Prešteta gotovina (€)<input type="number" min="0" step="0.01" value={value.closed ? value.counted_cash_eur : form.counted_cash_eur} onChange={(e) => setForm({ ...form, counted_cash_eur: e.target.value })} disabled={value.closed} required /></label>
        <label>Opomba<textarea value={value.closed ? value.notes || "" : form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} disabled={value.closed} placeholder="Npr. razlog za razliko" /></label>
        {value.closed ? <p className="locked-note">Zaključeno {value.closed_at ? new Date(value.closed_at).toLocaleString("sl-SI") : ""}. Posnetka ni mogoče spreminjati.</p> : <button className="primary-button">ZAKLJUČI POSLOVNI DAN</button>}
      </form>
      <section className="panel payment-breakdown">
        <div className="section-heading"><div><p className="eyebrow">Po načinu plačila</p><h2>Kontrolni seštevek</h2></div></div>
        <article><span>Gotovina</span><strong>+{money(value.cash_in_eur)} / −{money((value.cash_refund_eur || 0) + (value.cash_supplier_payment_eur || 0) + (value.cash_farm_expense_eur || 0))}</strong></article>
        <article><span>Kartice</span><strong>+{money(value.card_in_eur)} / −{money((value.card_refund_eur || 0) + (value.card_supplier_payment_eur || 0) + (value.card_farm_expense_eur || 0))}</strong></article>
        <article><span>Nakazila</span><strong>+{money(value.bank_transfer_in_eur)} / −{money((value.bank_transfer_refund_eur || 0) + (value.bank_transfer_supplier_payment_eur || 0) + (value.bank_transfer_farm_expense_eur || 0))}</strong></article>
        <p className="day-close-note">Odlivi vključujejo vračila kupcem, dejanska plačila dobaviteljem in splošne stroške kmetije. Stare ročno vnesene stroške brez načina plačila še vedno prikazuje samo denarni tok.</p>
      </section>
    </section>
    <section className="panel">
      <div className="section-heading"><div><p className="eyebrow">Nespremenljiva zgodovina</p><h2>Pretekli zaključki</h2></div><span>{closes.length} zapisov</span></div>
      {closes.length === 0 ? <p className="empty-state">Zaključen ni še noben poslovni dan.</p> : <div className="day-close-history">{closes.map((item) => <article key={item.id}><div><time>{item.business_date}</time><span>{item.retail_sale_count} hitrih prodaj · {item.payment_count} prejetih plačil · {item.refund_count} vračil · {item.supplier_payment_count || 0} plačil dobaviteljem · {item.farm_expense_count || 0} splošnih stroškov</span></div><div><span>Pričakovano {money(item.expected_cash_eur)}</span><strong className={item.difference_eur < 0 ? "negative" : "positive"}>{item.difference_eur >= 0 ? "+" : ""}{money(item.difference_eur)}</strong></div></article>)}</div>}
    </section>
  </>;
}

function PurchasingView({ suppliers, supplyItems, purchaseOrders, supplyUsages, beds, plantings, supplierForm, setSupplierForm, createSupplier, supplyItemForm, setSupplyItemForm, createSupplyItem, purchaseForm, setPurchaseForm, purchaseCart, addPurchaseItem, removePurchaseItem, createPurchaseOrder, receivePurchaseOrder, cancelPurchaseOrder, supplyUsageForm, setSupplyUsageForm, createSupplyUsage, supplierPaymentOrderId, beginSupplierPayment, cancelSupplierPayment, supplierPaymentForm, setSupplierPaymentForm, recordSupplierPayment }) {
  const categoryLabels = { seed: "Seme", fertilizer: "Gnojilo", packaging: "Embalaža", tools: "Orodje", fuel: "Gorivo", other: "Drugo" };
  const paymentLabels = { cash: "Gotovina", card: "Kartica", bank_transfer: "Nakazilo" };
  const statusLabels = { ordered: "Naročeno", received: "Prevzeto", cancelled: "Preklicano" };
  const paymentStatusLabels = { unpaid: "Neplačano", partial: "Delno plačano", paid: "Plačano" };
  const cartTotal = purchaseCart.reduce((sum, item) => sum + item.line_total_eur, 0);
  const openOrders = purchaseOrders.filter((item) => item.status === "ordered");
  const lowStock = supplyItems.filter((item) => item.low_stock);
  const selectedUsageBed = beds.find((item) => String(item.id) === String(supplyUsageForm.bed_id));
  const matchingPlantings = plantings.filter((item) => !selectedUsageBed || item.bed === selectedUsageBed.name);
  const plantingLabels = new Map(plantings.map((item) => [item.id, `${item.crop} ${item.variety}`]));
  return <>
    <section className="metric-grid purchasing-metrics">
      <article className="metric-card"><span>Odprta naročila</span><strong>{openOrders.length}</strong><small>{openOrders.reduce((sum, item) => sum + item.total_eur, 0).toFixed(2)} € naročene vrednosti</small></article>
      <article className="metric-card"><span>Nizka zaloga</span><strong className={lowStock.length ? "negative" : "positive"}>{lowStock.length}</strong><small>materialov za dopolnitev</small></article>
      <article className="metric-card"><span>Dobavitelji</span><strong>{suppliers.length}</strong><small>{supplyItems.length} materialov v katalogu</small></article>
    </section>
    <section className="purchasing-setup-grid">
      <form className="panel compact-form" onSubmit={createSupplier}>
        <div className="section-heading"><div><p className="eyebrow">Imenik</p><h2>Nov dobavitelj</h2></div></div>
        <label>Naziv<input value={supplierForm.name} onChange={(e) => setSupplierForm({ ...supplierForm, name: e.target.value })} required /></label>
        <label>Davčna številka<input value={supplierForm.tax_number} onChange={(e) => setSupplierForm({ ...supplierForm, tax_number: e.target.value })} /></label>
        <label>E-pošta<input type="email" value={supplierForm.email} onChange={(e) => setSupplierForm({ ...supplierForm, email: e.target.value })} /></label>
        <label>Telefon<input value={supplierForm.phone} onChange={(e) => setSupplierForm({ ...supplierForm, phone: e.target.value })} /></label>
        <button className="secondary-button">DODAJ DOBAVITELJA</button>
      </form>
      <form className="panel compact-form" onSubmit={createSupplyItem}>
        <div className="section-heading"><div><p className="eyebrow">Katalog in zaloga</p><h2>Nov material</h2></div></div>
        <label>Naziv<input value={supplyItemForm.name} onChange={(e) => setSupplyItemForm({ ...supplyItemForm, name: e.target.value })} required /></label>
        <label>Vrsta<select value={supplyItemForm.category} onChange={(e) => setSupplyItemForm({ ...supplyItemForm, category: e.target.value })}>{Object.entries(categoryLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Enota<input value={supplyItemForm.unit} onChange={(e) => setSupplyItemForm({ ...supplyItemForm, unit: e.target.value })} required /></label>
        <label>Začetna zaloga<input type="number" min="0" step="0.001" value={supplyItemForm.opening_stock} onChange={(e) => setSupplyItemForm({ ...supplyItemForm, opening_stock: e.target.value })} required /></label>
        <label>Opozorilo pod<input type="number" min="0" step="0.001" value={supplyItemForm.reorder_level} onChange={(e) => setSupplyItemForm({ ...supplyItemForm, reorder_level: e.target.value })} required /></label>
        <button className="secondary-button">DODAJ MATERIAL</button>
      </form>
    </section>
    <section className="panel purchase-entry">
      <div className="section-heading"><div><p className="eyebrow">Večpostavkovno naročilo</p><h2>Novo nabavno naročilo</h2><p className="muted">Prevzem poveča zalogo. Porabo na gredicah in dejanska delna ali celotna plačila evidentiraš ločeno spodaj.</p></div></div>
      <div className="purchase-order-details">
        <label>Dobavitelj<select value={purchaseForm.supplier_id} onChange={(e) => setPurchaseForm({ ...purchaseForm, supplier_id: e.target.value })} required><option value="">Izberi</option>{suppliers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Datum naročila<input type="date" value={purchaseForm.order_date} onChange={(e) => setPurchaseForm({ ...purchaseForm, order_date: e.target.value })} required /></label>
        <label>Predvideni prevzem<input type="date" min={purchaseForm.order_date} value={purchaseForm.expected_date} onChange={(e) => setPurchaseForm({ ...purchaseForm, expected_date: e.target.value })} /></label>
        <label>Način plačila<select value={purchaseForm.payment_method} onChange={(e) => setPurchaseForm({ ...purchaseForm, payment_method: e.target.value })}><option value="bank_transfer">Nakazilo</option><option value="card">Kartica</option><option value="cash">Gotovina</option></select></label>
      </div>
      <form className="purchase-line-form" onSubmit={addPurchaseItem}>
        <label>Material<select value={purchaseForm.supply_item_id} onChange={(e) => setPurchaseForm({ ...purchaseForm, supply_item_id: e.target.value })} required><option value="">Izberi</option>{supplyItems.map((item) => <option key={item.id} value={item.id}>{item.name} · zaloga {item.stock_quantity} {item.unit}</option>)}</select></label>
        <label>Količina<input type="number" min="0.001" step="0.001" value={purchaseForm.quantity} onChange={(e) => setPurchaseForm({ ...purchaseForm, quantity: e.target.value })} required /></label>
        <label>Cena/enoto (€)<input type="number" min="0.0001" step="0.0001" value={purchaseForm.unit_price_eur} onChange={(e) => setPurchaseForm({ ...purchaseForm, unit_price_eur: e.target.value })} required /></label>
        <button className="secondary-button">DODAJ POSTAVKO</button>
      </form>
      <div className="purchase-cart">{purchaseCart.length === 0 ? <p className="empty-state">Naročilo še nima postavk.</p> : purchaseCart.map((item) => <article key={item.supply_item_id}><div><strong>{item.name}</strong><span>{item.quantity} {item.unit} × {item.unit_price_eur.toFixed(4)} €</span></div><strong>{item.line_total_eur.toFixed(2)} €</strong><button className="icon-button" type="button" onClick={() => removePurchaseItem(item.supply_item_id)}>✕</button></article>)}</div>
      <label>Opomba<textarea value={purchaseForm.notes} onChange={(e) => setPurchaseForm({ ...purchaseForm, notes: e.target.value })} /></label>
      <div className="purchase-checkout"><span>Skupaj</span><strong>{cartTotal.toFixed(2)} €</strong><button className="primary-button" type="button" disabled={!purchaseCart.length || !purchaseForm.supplier_id} onClick={createPurchaseOrder}>USTVARI NAROČILO</button></div>
    </section>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Material za delo</p><h2>Zaloga potrebščin</h2></div><span>{lowStock.length} pod minimumom</span></div>
      {supplyItems.length === 0 ? <p className="empty-state">Katalog materiala je prazen.</p> : <div className="supply-stock-grid">{supplyItems.map((item) => <article key={item.id} className={item.low_stock ? "low" : ""}><span>{categoryLabels[item.category] || item.category}</span><strong>{item.name}</strong><b>{item.stock_quantity} {item.unit}</b><small>Opozorilo pri {item.reorder_level} {item.unit}</small></article>)}</div>}
    </section>
    <section className="supply-usage-grid">
      <form className="panel supply-usage-form" onSubmit={createSupplyUsage}>
        <div className="section-heading"><div><p className="eyebrow">Dejanska poraba</p><h2>Knjiži material na gredico</h2><p className="muted">Količina se odšteje iz zaloge, njena vrednost pa se prišteje stroškom izbrane gredice.</p></div></div>
        <label>Material<select value={supplyUsageForm.supply_item_id} onChange={(e) => setSupplyUsageForm({ ...supplyUsageForm, supply_item_id: e.target.value })} required><option value="">Izberi</option>{supplyItems.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.stock_quantity} {item.unit} na zalogi</option>)}</select></label>
        <label>Gredica<select value={supplyUsageForm.bed_id} onChange={(e) => setSupplyUsageForm({ ...supplyUsageForm, bed_id: e.target.value, planting_id: "" })} required><option value="">Izberi</option>{beds.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Setev (neobvezno)<select value={supplyUsageForm.planting_id} onChange={(e) => setSupplyUsageForm({ ...supplyUsageForm, planting_id: e.target.value })}><option value="">Samo gredica</option>{matchingPlantings.map((item) => <option key={item.id} value={item.id}>{item.crop} {item.variety} · {item.status === "active" ? "aktivna" : "zaključena"}</option>)}</select></label>
        <label>Datum porabe<input type="date" value={supplyUsageForm.usage_date} onChange={(e) => setSupplyUsageForm({ ...supplyUsageForm, usage_date: e.target.value })} required /></label>
        <label>Količina<input type="number" min="0.001" step="0.001" value={supplyUsageForm.quantity} onChange={(e) => setSupplyUsageForm({ ...supplyUsageForm, quantity: e.target.value })} required /></label>
        <label>Strošek/enoto (€)<input type="number" min="0.0001" step="0.0001" value={supplyUsageForm.unit_cost_eur} onChange={(e) => setSupplyUsageForm({ ...supplyUsageForm, unit_cost_eur: e.target.value })} placeholder="Samodejno iz prevzemov" /></label>
        <label className="wide">Opomba<input value={supplyUsageForm.notes} onChange={(e) => setSupplyUsageForm({ ...supplyUsageForm, notes: e.target.value })} placeholder="Npr. dognojevanje po presajanju" /></label>
        <p className="usage-cost-note">Če ceno pustiš prazno, se uporabi tehtano povprečje vseh prevzetih nabav. Pri začetni zalogi brez prevzema ceno vnesi ročno.</p>
        <button className="primary-button">KNJIŽI PORABO</button>
      </form>
      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">Razporeditev stroškov</p><h2>Zadnja poraba</h2></div><span>{supplyUsages.length} zapisov</span></div>
        {supplyUsages.length === 0 ? <p className="empty-state">Poraba materiala še ni evidentirana.</p> : <div className="supply-usage-history">{supplyUsages.slice(0, 12).map((usage) => <article key={usage.id}><div><time>{usage.usage_date}</time><strong>{usage.supply_item}</strong><span>Gredica {usage.bed}{usage.planting_id ? ` · ${plantingLabels.get(usage.planting_id) || "setev"}` : ""}</span>{usage.notes && <small>{usage.notes}</small>}</div><div><strong>{usage.quantity} {usage.unit}</strong><span>{usage.total_cost_eur.toFixed(2)} €</span><small>{usage.unit_cost_eur.toFixed(4)} €/enoto</small></div></article>)}</div>}
      </section>
    </section>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Nabavna zgodovina</p><h2>Naročila dobaviteljem</h2></div><span>{purchaseOrders.length} zapisov</span></div>
      {purchaseOrders.length === 0 ? <p className="empty-state">Nabavno naročilo še ni ustvarjeno.</p> : <div className="purchase-order-list">{purchaseOrders.map((order) => <article key={order.id} className={order.status}><div className="purchase-order-head"><div><div className="purchase-states"><span className={`purchase-state ${order.status}`}>{statusLabels[order.status]}</span><span className={`purchase-state payment-${order.payment_status}`}>{paymentStatusLabels[order.payment_status]}</span></div><strong>{order.number} · {order.supplier.name}</strong><span>Naročeno {order.order_date}{order.expected_date ? ` · pričakovano ${order.expected_date}` : ""}{order.received_on ? ` · prevzeto ${order.received_on}` : ""}</span></div><div><strong>{order.total_eur.toFixed(2)} €</strong><span>{order.paid_eur.toFixed(2)} € plačano · {order.outstanding_eur.toFixed(2)} € odprto</span></div></div><div className="purchase-order-lines">{order.items.map((item) => <span key={item.id}>{item.name} · {item.quantity} {item.unit} × {item.unit_price_eur.toFixed(4)} €</span>)}</div>{order.payments.length > 0 && <div className="payment-history supplier-payment-history">{order.payments.map((payment) => <span key={payment.id}>{payment.payment_date} · {payment.amount_eur.toFixed(2)} € · {paymentLabels[payment.payment_method]}{payment.notes ? ` · ${payment.notes}` : ""}</span>)}</div>}{supplierPaymentOrderId === order.id ? <form className="payment-form supplier-payment-form" onSubmit={recordSupplierPayment}><label>Datum<input type="date" min={order.order_date} value={supplierPaymentForm.payment_date} onChange={(e) => setSupplierPaymentForm({ ...supplierPaymentForm, payment_date: e.target.value })} required /></label><label>Znesek (€)<input type="number" min="0.01" max={order.outstanding_eur} step="0.01" value={supplierPaymentForm.amount_eur} onChange={(e) => setSupplierPaymentForm({ ...supplierPaymentForm, amount_eur: e.target.value })} required /></label><label>Način<select value={supplierPaymentForm.payment_method} onChange={(e) => setSupplierPaymentForm({ ...supplierPaymentForm, payment_method: e.target.value })}>{Object.entries(paymentLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Opomba<input value={supplierPaymentForm.notes} onChange={(e) => setSupplierPaymentForm({ ...supplierPaymentForm, notes: e.target.value })} /></label><div className="supplier-payment-actions"><button type="button" className="text-button" onClick={cancelSupplierPayment}>PREKLIČI</button><button className="primary-button">SHRANI PLAČILO</button></div></form> : <div className="order-actions">{order.status === "ordered" && <><button className="secondary-button" onClick={() => receivePurchaseOrder(order)}>PREVZEM</button><button className="text-button danger-text" onClick={() => cancelPurchaseOrder(order)}>PREKLIČI</button></>}{order.status !== "cancelled" && order.outstanding_eur > 0 && <button className="primary-button" onClick={() => beginSupplierPayment(order)}>EVIDENTIRAJ PLAČILO</button>}</div>}</article>)}</div>}
    </section>
  </>;
}

const babyLeafProfile = (cropName = "") => {
  const name = cropName.toLocaleLowerCase("sl-SI");
  const profiles = [
    ["redkv", 8, 1.6, 22, 1], ["blit", 5, 1.8, 35, 3], ["brokol", 5, 1.2, 25, 1],
    ["ohrovt", 4, 1.3, 30, 2], ["špina", 3.5, 1.5, 32, 2], ["spinac", 3.5, 1.5, 32, 2],
    ["rukol", 2.2, 1.2, 24, 2], ["motovil", 3, 1, 45, 1], ["mizun", 3, 1.2, 25, 2],
    ["tatsoi", 3, 1.3, 28, 2], ["pak choi", 3.5, 1.4, 28, 2], ["gorči", 3, 1.2, 24, 2],
    ["komats", 3, 1.3, 27, 2], ["endiv", 2, 1.3, 30, 1], ["radič", 2.5, 1.2, 32, 1],
    ["solat", 1.5, 1.4, 28, 1],
  ];
  const match = profiles.find(([keyword]) => name.includes(keyword));
  const [, seedRate, yieldRate, days, cuts] = match || ["", 3, 1.3, 28, 1];
  return { seedRate, yieldRate, days, cuts };
};

const standardYieldPerPlant = (cropName = "") => {
  const name = cropName.toLocaleLowerCase("sl-SI");
  if (name.includes("paradiž")) return 4.5;
  if (name.includes("buč")) return 5;
  if (name.includes("paprik")) return 2.2;
  if (name.includes("solat")) return 0.25;
  if (name.includes("fižol")) return 0.18;
  if (name.includes("koren")) return 0.12;
  if (name.includes("čebul")) return 0.12;
  if (name.includes("redkv")) return 0.04;
  return 0.3;
};

function GredicnikView({ crops, beds, savePlan }) {
  const [form, setForm] = useState({ bed_id: "", crop_id: "", variety_id: "", region: "centralna", environment: "outdoor", altitude_m: "300", mode: "standard", rows: "3", row_spacing_cm: "25", plant_spacing_cm: "25", sowing_date: today, succession_count: "1", succession_interval_days: "14" });
  const [saving, setSaving] = useState(false);
  const selectedBed = beds.find((bed) => String(bed.id) === String(form.bed_id));
  const selectedCrop = crops.find((crop) => String(crop.id) === String(form.crop_id));
  const selectedVariety = selectedCrop?.varieties.find((variety) => String(variety.id) === String(form.variety_id));
  const timing = plantingTiming(selectedVariety, form.environment, form.sowing_date, form.region);
  const babyLeaf = form.mode.startsWith("baby");
  const spacingOptions = useMemo(
    () => getGredicnikSpacingOptions(selectedCrop, selectedVariety),
    [selectedCrop, selectedVariety],
  );
  const spacingRecommendation = spacingOptions[form.mode] || getGredicnikSpacing(selectedCrop, selectedVariety, form.mode);

  function withSpacingRecommendation(current, crop, variety, mode) {
    const recommendation = getGredicnikSpacing(crop, variety, mode);
    return {
      ...current,
      mode,
      rows: String(recommendation.rows),
      row_spacing_cm: String(recommendation.rowSpacingCm),
      plant_spacing_cm: String(recommendation.plantSpacingCm),
    };
  }

  useEffect(() => {
    if (!form.bed_id && beds[0]) setForm((current) => ({ ...current, bed_id: String(beds[0].id) }));
  }, [beds, form.bed_id]);

  useEffect(() => {
    if (!form.crop_id && crops[0]) {
      setForm((current) => {
        const crop = crops[0];
        const variety = crop.varieties[0];
        const mode = crop.category === "Baby leaf" ? "baby6" : "standard";
        return withSpacingRecommendation({ ...current, crop_id: String(crop.id), variety_id: String(variety?.id || ""), succession_interval_days: String(variety?.succession_interval_days || current.succession_interval_days) }, crop, variety, mode);
      });
    }
  }, [crops, form.crop_id]);

  const result = useMemo(() => {
    const width = Number(selectedBed?.width_m || 0);
    const length = Number(selectedBed?.length_m || 0);
    const area = Number(selectedBed?.area_m2 || width * length);
    const fixedRows = form.mode.endsWith("10") || form.mode.endsWith("12") ? 10 : form.mode.endsWith("6") ? 6 : null;
    const rows = fixedRows || Math.max(1, Number(form.rows) || Math.floor(width / (Number(form.row_spacing_cm) / 100)) || 1);
    const occupiedWidthCm = Math.max(0, rows - 1) * Number(form.row_spacing_cm);
    const edgeMarginCm = (width * 100 - occupiedWidthCm) / 2;
    const layoutFits = edgeMarginCm >= 8;
    const plantsPerRow = Math.max(1, Math.floor(length / Math.max(0.01, Number(form.plant_spacing_cm) / 100)));
    const plants = rows * plantsPerRow;
    const profile = babyLeafProfile(selectedCrop?.name);
    const catalogSeedRate = Number(selectedVariety?.seed_rate_g_m2);
    const seedRate = Number.isFinite(catalogSeedRate) && catalogSeedRate > 0 ? catalogSeedRate : profile.seedRate;
    const seedGrams = area * seedRate;
    const expectedYield = babyLeaf ? area * profile.yieldRate * profile.cuts : plants * standardYieldPerPlant(selectedCrop?.name);
    const regionAdjustments = { primorska: -12, panonska: -4, centralna: 0, alpska: 12 };
    const altitudeAdjustment = Math.max(-3, Math.round((Number(form.altitude_m || 300) - 300) / 60));
    const climateAdjustment = regionAdjustments[form.region] + altitudeAdjustment;
    const varietyDays = Number(maturityDaysForDate(selectedVariety, form.sowing_date));
    const catalogBabyDays = Number(selectedVariety?.days_baby);
    const babyDays = Number.isFinite(catalogBabyDays) && catalogBabyDays > 0 ? catalogBabyDays : profile.days;
    const harvestDays = Math.max(7, (babyLeaf ? babyDays : Number.isFinite(varietyDays) ? varietyDays : 60) + climateAdjustment);
    const harvest = new Date(`${form.sowing_date}T12:00:00`); harvest.setDate(harvest.getDate() + harvestDays);
    const expectedHarvestDate = Number.isNaN(harvest.getTime()) ? "—" : harvest.toLocaleDateString("sl-SI");
    return { width, length, area, rows, occupiedWidthCm, edgeMarginCm, layoutFits, plantsPerRow, plants, seeds: Math.ceil(plants * 1.15), seedGrams, expectedYield, climateAdjustment, harvestDays, expectedHarvestDate, ...profile, seedRate, days: babyDays };
  }, [selectedBed, selectedCrop, selectedVariety, form.mode, form.rows, form.row_spacing_cm, form.plant_spacing_cm, form.region, form.altitude_m, form.sowing_date, babyLeaf]);

  function changeCrop(cropId) {
    const crop = crops.find((item) => String(item.id) === String(cropId));
    const variety = crop?.varieties[0];
    const mode = crop?.category === "Baby leaf" ? "baby6" : form.mode.startsWith("baby") ? "standard" : form.mode;
    setForm(withSpacingRecommendation({ ...form, crop_id: cropId, variety_id: String(variety?.id || ""), succession_interval_days: String(variety?.succession_interval_days || form.succession_interval_days) }, crop, variety, mode));
  }

  function changeVariety(varietyId) {
    const variety = selectedCrop?.varieties.find((item) => String(item.id) === String(varietyId));
    setForm(withSpacingRecommendation({ ...form, variety_id: varietyId, succession_interval_days: String(variety?.succession_interval_days || form.succession_interval_days) }, selectedCrop, variety, form.mode));
  }

  function changeMode(mode) {
    setForm(withSpacingRecommendation(form, selectedCrop, selectedVariety, mode));
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    const modeLabel = GREDICNIK_MODES.find((item) => item.value === form.mode)?.label || form.mode;
    const regionLabels = { primorska: "Primorska", panonska: "Panonska Slovenija", centralna: "Osrednja Slovenija", alpska: "Alpski svet" };
    const environmentLabel = form.environment === "protected" ? "neogrevan tunel" : "na prostem";
    const notes = `Gredičnik: ${modeLabel}; oprema ${spacingRecommendation.equipment}; ${spacingRecommendation.setup}; gredica ${result.width.toFixed(2)} × ${result.length.toFixed(2)} m (${result.area.toFixed(2)} m²); ${regionLabels[form.region]}, ${form.altitude_m} m n. v.; ${environmentLabel}; izbrani termin ${timing.recommended ? "je v priporočenem oknu" : "je zunaj priporočenega okna"} (${timing.monthsLabel}); podnebni popravek ${result.climateAdjustment >= 0 ? "+" : ""}${result.climateAdjustment} dni; razmik vrst ${form.row_spacing_cm} cm; odmik od robov ${result.edgeMarginCm.toFixed(1)} cm; razmik v vrsti ${form.plant_spacing_cm} cm; ${babyLeaf ? `${result.seedGrams.toFixed(1)} g semena; do ${result.cuts} rezov` : `${result.plants} rastlin; približno ${result.seeds} semen`}.`;
    await savePlan({ bed_id: Number(form.bed_id), crop_id: Number(form.crop_id), variety_id: Number(form.variety_id), sowing_date: form.sowing_date, transplant_date: null, expected_yield_kg: Number(result.expectedYield.toFixed(2)), succession_count: Number(form.succession_count), succession_interval_days: Number(form.succession_interval_days), notes });
    setSaving(false);
  }

  const ready = selectedBed && selectedCrop && selectedVariety && result.expectedYield > 0 && result.layoutFits;
  return <>
    <section className="panel gredicnik-heading">
      <div><p className="eyebrow">Pridelovalni kalkulator</p><h2>Gredičnik</h2><p className="muted">Izračunaj razpored, količino semena in pričakovani pridelek na obstoječih GrowMasterjevih gredicah ter rezultat neposredno dodaj v sezonski načrt.</p></div>
      <span className="module-badge">PRAVI MODUL GROWMASTERJA</span>
    </section>
    {beds.length === 0 || crops.length === 0 ? <section className="panel"><p className="empty-state">Za uporabo Gredičnika najprej dodaj vsaj eno gredico ter kulturo s sorto.</p></section> :
      <form className="gredicnik-layout" onSubmit={submit}>
        <section className="panel gredicnik-form">
          <div className="section-heading"><div><p className="eyebrow">1. Osnova</p><h2>Gredica in kultura</h2></div></div>
          <div className="gredicnik-fields">
            <label>Gredica<select value={form.bed_id} onChange={(e) => setForm({ ...form, bed_id: e.target.value })} required>{beds.map((bed) => <option key={bed.id} value={bed.id}>{bed.name} · {bed.width_m} × {bed.length_m} m</option>)}</select></label>
            <label>Kultura<select value={form.crop_id} onChange={(e) => changeCrop(e.target.value)} required>{crops.map((crop) => <option key={crop.id} value={crop.id}>{crop.name}</option>)}</select></label>
            <label>Sorta<select value={form.variety_id} onChange={(e) => changeVariety(e.target.value)} required>{(selectedCrop?.varieties || []).map((variety) => <option key={variety.id} value={variety.id}>{variety.name}</option>)}</select></label>
            <label>Datum {timing.methodLabel === "presajanje" ? "presajanja" : "setve"}<input type="date" value={form.sowing_date} onChange={(e) => setForm({ ...form, sowing_date: e.target.value })} required /></label>
            <label>Način pridelave<select value={form.environment} onChange={(e) => setForm({ ...form, environment: e.target.value })}>{PLANTING_ENVIRONMENTS.map((environment) => <option key={environment.value} value={environment.value}>{environment.label}</option>)}</select></label>
            <label>Pridelovalna regija<select value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })}><option value="centralna">Osrednja Slovenija</option><option value="primorska">Primorska</option><option value="panonska">Panonska Slovenija</option><option value="alpska">Alpski svet</option></select></label>
            <label>Nadmorska višina (m)<input type="number" min="0" max="2000" step="10" value={form.altitude_m} onChange={(e) => setForm({ ...form, altitude_m: e.target.value })} required /></label>
          </div>
          <div className={`planting-calendar-recommendation ${timing.recommended ? "recommended" : "outside"}`}>
            <div><span>Najprimernejši čas za {timing.methodLabel} {timing.environmentLabel}</span><strong>{timing.monthsLabel}</strong></div>
            <b>{timing.recommended ? "IZBRANI DATUM JE PRIMEREN" : "PREVERI IZBRANI DATUM"}</b>
            <p>{selectedVariety?.planting_calendar_note}</p>
            <div className="tolerance-badges"><small>Vročina: {toleranceLabel(selectedVariety?.heat_tolerance)}</small><small>Mraz: {toleranceLabel(selectedVariety?.cold_tolerance)}</small>{selectedVariety?.succession_interval_days && <small>Nov turnus: {selectedVariety.succession_interval_days} dni</small>}</div>
            <small>{timing.regionNote} Dejanski termin vedno prilagodi trenutni slani, temperaturi tal in zaščiti.</small>
            {selectedVariety?.calendar_source_url && <a href={selectedVariety.calendar_source_url} target="_blank" rel="noreferrer">Odpri vir koledarja ↗</a>}
          </div>
          <div className="section-heading gredicnik-step"><div><p className="eyebrow">2. Način</p><h2>Razpored setve</h2></div></div>
          <div className="mode-picker">
            {GREDICNIK_MODES.map(({ value, label }) => {
              const option = spacingOptions[value];
              return <button type="button" key={value} className={`${form.mode === value ? "active" : ""}${option?.suitable === false ? " limited" : ""}`} onClick={() => changeMode(value)}><strong>{label}</strong><small>{option ? `${String(option.plantSpacingCm).replace(".", ",")} cm · ${option.equipmentShort}` : "—"}</small>{option?.recommended && <em>priporočeno</em>}</button>;
            })}
          </div>
          <div className={`spacing-recommendation ${spacingRecommendation.suitable && result.layoutFits ? "" : "limited"}`}>
            <div><span>Priporočilo za izbrano sorto</span><strong>{String(spacingRecommendation.plantSpacingCm).replace(".", ",")} cm v vrsti</strong></div>
            <b>{spacingRecommendation.equipment}</b>
            <p>{spacingRecommendation.setup}</p>
            <small>{spacingRecommendation.note}</small>
            <small>{result.layoutFits
              ? `Na izbrani gredici širine ${(result.width * 100).toFixed(0)} cm ostane približno ${result.edgeMarginCm.toFixed(1).replace(".", ",")} cm do vsakega roba.`
              : `Razpored je preširok: do vsakega roba mora ostati najmanj 8 cm. Zmanjšaj število vrst ali razmik med njimi.`}</small>
          </div>
          <div className="gredicnik-fields compact-fields">
            <label>Število vrst<input type="number" min="1" max="30" value={result.rows} disabled={form.mode !== "standard"} onChange={(e) => setForm({ ...form, rows: e.target.value })} /></label>
            <label>Razmik med vrstami (cm)<input type="number" min="1" step="0.1" value={form.row_spacing_cm} onChange={(e) => setForm({ ...form, row_spacing_cm: e.target.value })} required /></label>
            <label>Razmik v vrsti (cm)<input type="number" min="0.5" step="0.1" value={form.plant_spacing_cm} onChange={(e) => setForm({ ...form, plant_spacing_cm: e.target.value })} required /></label>
          </div>
          <div className="section-heading gredicnik-step"><div><p className="eyebrow">3. Ponavljanje</p><h2>Succession planting</h2></div></div>
          <div className="gredicnik-fields compact-fields">
            <label>Število zaporednih setev<input type="number" min="1" max="20" value={form.succession_count} onChange={(e) => setForm({ ...form, succession_count: e.target.value })} required /></label>
            <label>Razmik med setvami (dni)<input type="number" min="1" value={form.succession_interval_days} onChange={(e) => setForm({ ...form, succession_interval_days: e.target.value })} required /></label>
          </div>
        </section>
        <aside className="panel gredicnik-result">
          <div><p className="eyebrow">Izračun</p><h2>{selectedBed?.name || "Gredica"}</h2><p className="muted">{selectedCrop?.name} {selectedVariety?.name ? `· ${selectedVariety.name}` : ""}</p></div>
          <div className="gredicnik-metrics">
            <article><span>Površina</span><strong>{result.area.toFixed(1)} m²</strong></article>
            <article><span>Vrst</span><strong>{result.rows}</strong></article>
            {babyLeaf ? <><article><span>Semena</span><strong>{result.seedGrams.toFixed(1)} g</strong></article><article><span>Prvi rez</span><strong>~ {result.days} dni</strong></article><article><span>Možni rezi</span><strong>{result.cuts}</strong></article></> : <><article><span>Rastlin</span><strong>{result.plants}</strong></article><article><span>Semena + 15 %</span><strong>{result.seeds}</strong></article></>}
            <article className="yield-metric"><span>Pričakovani pridelek</span><strong>{result.expectedYield.toFixed(1)} kg</strong></article>
            <article className="harvest-metric"><span>Okvirna prva žetev</span><strong>{result.expectedHarvestDate}</strong><small>{result.harvestDays} dni po {timing.methodLabel === "presajanje" ? "presajanju" : "setvi"} · podnebni popravek {result.climateAdjustment >= 0 ? "+" : ""}{result.climateAdjustment} dni</small></article>
          </div>
          {(form.mode === "baby10" || form.mode === "seeder10") && spacingRecommendation.equipment === "6 Row Seeder v2" && <p className="seeder-note">Deset vrst se izvede z dvema prilagojenima prehodoma po pet setvenih linij. Pri razmiku 6,4 cm na 80 cm gredici ostane približno 11,2 cm do vsakega roba.</p>}
          <button className="primary-button save-gredicnik" disabled={!ready || saving}>{saving ? "SHRANJUJEM …" : "DODAJ V GROWMASTERJEV PLAN"}</button>
          <p className="calculation-note">Ocene semena in pridelka so načrtovalske vrednosti. Po prvih žetvah jih primerjaj z dejanskim rezultatom sorte in lokacije.</p>
        </aside>
      </form>}
  </>;
}

function PlanningView({ crops, beds, plans, calendar, forecast, form, setForm, selectedCrop, changeCrop, createPlan, activatePlan, cancelPlan, start, setStart, end, setEnd }) {
  return <>
    <section className="panel"><div className="section-heading"><div><p className="eyebrow">Sezonski načrt</p><h2>Načrtuj setev ali serijo</h2></div></div>
      <form className="planning-form" onSubmit={createPlan}>
        <label>Gredica<select value={form.bed_id} onChange={(e) => setForm({ ...form, bed_id: e.target.value })} required>{beds.map((bed) => <option key={bed.id} value={bed.id}>{bed.name} · {bed.area_m2} m²</option>)}</select></label>
        <label>Kultura<select value={form.crop_id} onChange={changeCrop} required>{crops.map((crop) => <option key={crop.id} value={crop.id}>{crop.name}</option>)}</select></label>
        <label>Sorta<select value={form.variety_id} onChange={(e) => setForm({ ...form, variety_id: e.target.value })} required>{(selectedCrop?.varieties || []).map((item) => <option key={item.id} value={item.id}>{item.name} · {maturityDaysForDate(item, form.sowing_date)} dni ({maturitySeasonForDate(form.sowing_date).label})</option>)}</select></label>
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

function DataSafetyView({ status, readiness, restoreFile, setRestoreFile, confirmation, setConfirmation, restoreData }) {
  const backups = status.automatic_backups || [];
  const dailyBackups = status.daily_backups || [];
  const storageLocation = status.storage_location ? String(status.storage_location).replaceAll("/", "\\") : null;
  const sizeLabel = (bytes) => bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(2)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return <>
    <section className="panel data-safety-heading">
      <div><p className="eyebrow">Varnost podatkov</p><h2>Varnostne kopije in obnovitev</h2><p className="muted">GrowMaster vsak dan med delovanjem shrani novo prenosljivo kopijo. Pred vsako obnovitvijo dodatno ohrani trenutno stanje, zato se lahko vrneš nazaj.</p></div>
      <span className={`readiness-summary ${readiness.operational_ready ? "ready" : "blocked"}`}>{readiness.operational_ready ? "✓ PRIPRAVLJENO ZA DELO" : "⚠ POTREBEN JE PREGLED"}</span>
    </section>
    <section className="panel readiness-panel">
      <div className="section-heading"><div><p className="eyebrow">Produkcijski pregled</p><h2>Ali je GrowMaster pripravljen?</h2><p className="muted">Ob vsakem obisku se preverijo povezava z bazo, različica podatkov, zapisovanje in veljavnost kopij ter osnovna nastavitev kmetije.</p></div><span>Različica {readiness.version || "—"}</span></div>
      <div className="readiness-grid">{(readiness.checks || []).map((check) => <article className={`readiness-check ${check.status}`} key={check.key}><span className="readiness-icon">{check.status === "ready" ? "✓" : check.status === "attention" ? "!" : "×"}</span><div><strong>{check.label}</strong><small>{check.detail}</small>{!check.required && <em>Potrebno šele pred prvim računom pravni osebi</em>}</div></article>)}</div>
    </section>
    <section className="metric-grid data-safety-metrics">
      <article className="metric-card"><span>Različica podatkov</span><strong>{status.schema_revision?.split("_")[0] || "—"}</strong><small>nadgradnje se izvedejo samodejno in samo enkrat</small></article>
      <article className="metric-card"><span>Vsi zapisi</span><strong>{status.record_count || 0}</strong><small>v {status.table_count || 0} povezanih podatkovnih sklopih</small></article>
      <article className="metric-card"><span>Dnevne kopije</span><strong>{dailyBackups.length}</strong><small>samodejno se ohrani zadnjih {status.daily_backup_retention || 14} dni</small></article>
      <article className="metric-card"><span>Povratne kopije</span><strong>{backups.length}</strong><small>samodejno se ohrani zadnjih 10 obnovitev</small></article>
    </section>
    <section className="panel storage-location-card">
      <div>
        <p className="eyebrow">Mesto shranjevanja</p>
        <h2>Mapa baze in varnostnih kopij</h2>
        <p className="muted">GrowMaster med selitvijo aplikacijo varno ustavi, preveri kopirane podatke in jo nato ponovno zažene. Stara kopija ostane nedotaknjena.</p>
        <span className="storage-path">{storageLocation || "Trenutno mesto upravlja Docker"}</span>
      </div>
      {status.storage_move_supported && !isNativeApp
        ? <button type="button" className="secondary-button" onClick={() => window.location.assign("growmaster-storage://move")}>IZBERI NOVO MAPO</button>
        : <small>Mapo lahko prestaviš na računalniku z nameščeno Windows aplikacijo GrowMaster.</small>}
    </section>
    <section className="panel">
      <div className="section-heading"><div><p className="eyebrow">Vsakodnevna zaščita</p><h2>Samodejne dnevne kopije</h2><p className="muted">Nova kopija nastane ob zagonu in nato enkrat na dan, dokler GrowMaster deluje. Vsebuje poslovne podatke, ne pa gesla ali aktivnih prijav.</p></div><span>{dailyBackups.length} shranjenih</span></div>
      {dailyBackups.length === 0 ? <p className="empty-state">Prva dnevna kopija bo ustvarjena ob naslednjem zagonu GrowMasterja.</p> : <div className="automatic-backup-list">{dailyBackups.map((backup) => <article key={backup.filename}><div><strong>{new Date(`${backup.backup_date}T12:00:00`).toLocaleDateString("sl-SI")}</strong><span>{backup.filename} · {sizeLabel(backup.size_bytes)}</span></div><ProtectedDownloadButton path={`/api/system/backups/daily/${encodeURIComponent(backup.filename)}`} filename={backup.filename}>PRENESI</ProtectedDownloadButton></article>)}</div>}
    </section>
    <section className="data-safety-grid">
      <section className="panel backup-export-card">
        <div><p className="eyebrow">Shrani zunaj aplikacije</p><h2>Nova varnostna kopija</h2><p className="muted">Datoteka vsebuje gredice, pridelke, prodajo, račune, dokumente, zalogo in finančne zapise. Shrani jo na varen disk ali v svojo oblačno mapo.</p></div>
        <ProtectedDownloadButton className="primary-button backup-download" path="/api/system/backups/export" filename={`growmaster-kopija-${today}.json`}>PRENESI CELOTNO KOPIJO</ProtectedDownloadButton>
      </section>
      <form className="panel restore-form" onSubmit={restoreData}>
        <div><p className="eyebrow">Nadzorovana obnovitev</p><h2>Obnovi iz datoteke</h2><p className="muted">Datoteka se pred obnovitvijo preveri. Če je poškodovana ali iz druge različice, se podatki ne spremenijo.</p></div>
        <label>GrowMaster kopija<input type="file" accept="application/json,.json" onChange={(e) => setRestoreFile(e.target.files?.[0] || null)} required /></label>
        {restoreFile && <span className="selected-backup">Izbrano: {restoreFile.name} · {sizeLabel(restoreFile.size)}</span>}
        <label>Za potrditev vpiši OBNOVI<input value={confirmation} onChange={(e) => setConfirmation(e.target.value)} autoComplete="off" /></label>
        <button className="danger-button restore-button" disabled={!restoreFile || confirmation !== "OBNOVI"}>OBNOVI PODATKE</button>
      </form>
    </section>
    <section className="panel">
      <div className="section-heading"><div><p className="eyebrow">Samodejna zaščita</p><h2>Povratne kopije pred obnovitvijo</h2></div><span>{backups.length} shranjenih</span></div>
      {backups.length === 0 ? <p className="empty-state">Povratna kopija bo ustvarjena tik pred prvo obnovitvijo.</p> : <div className="automatic-backup-list">{backups.map((backup) => <article key={backup.filename}><div><strong>{new Date(backup.created_at).toLocaleString("sl-SI")}</strong><span>{backup.filename} · {sizeLabel(backup.size_bytes)}</span></div><ProtectedDownloadButton path={`/api/system/backups/automatic/${encodeURIComponent(backup.filename)}`} filename={backup.filename}>PRENESI</ProtectedDownloadButton></article>)}</div>}
      <p className="backup-privacy-note">Varnostne kopije lahko vsebujejo osebne in finančne podatke kupcev, nikoli pa gesla ali aktivne prijave. Hrani jih na mestu, do katerega nima dostopa nepooblaščena oseba.</p>
    </section>
  </>;
}

function ConnectionView({ onConnected }) {
  const [serverUrl, setServerUrl] = useState("");
  const [checking, setChecking] = useState(false);
  const [connectionError, setConnectionError] = useState("");

  async function connect(event) {
    event.preventDefault();
    setChecking(true);
    setConnectionError("");
    try {
      const result = await testServerConnection(serverUrl);
      onConnected(result.serverUrl);
    } catch (error) {
      setConnectionError(error.message || "Povezava ni uspela.");
    } finally {
      setChecking(false);
    }
  }

  return <main className="auth-shell connection-shell">
    <section className="auth-intro">
      <img className="auth-logo" src="/icons/growmaster-192.png" alt="" />
      <p className="eyebrow">Mobilni GrowMaster</p>
      <h1>Poveži svojo kmetijo</h1>
      <p>Vpiši naslov GrowMasterja na računalniku ali zasebnem spletnem strežniku. Telefon in računalnik bosta nato uporabljala iste podatke.</p>
    </section>
    <form className="auth-card" onSubmit={connect}>
      <div><p className="eyebrow">Prva povezava</p><h2>Naslov strežnika</h2></div>
      <label>Naslov GrowMasterja<input type="url" inputMode="url" value={serverUrl} onChange={(event) => setServerUrl(event.target.value)} placeholder="https://moja-kmetija.example.si" autoCapitalize="none" autoCorrect="off" required autoFocus /></label>
      <p className="auth-hint">Za uporabo samo v domačem omrežju je lahko naslov npr. http://192.168.1.20:3000. Za uporabo kjerkoli priporočamo zasebni naslov HTTPS.</p>
      {connectionError && <div className="message error">⚠ {connectionError}</div>}
      <button className="primary-button" type="submit" disabled={checking}>{checking ? "PREVERJAM …" : "POVEŽI"}</button>
    </form>
  </main>;
}

function AuthenticationView({ auth, form, setForm, submit, error, changeServer, serverUrl }) {
  const setup = !auth.configured;
  return <main className="auth-shell">
    <section className="auth-intro">
      <img className="auth-logo" src="/icons/growmaster-192.png" alt="" />
      <p className="eyebrow">Lokalno upravljanje kmetije</p>
      <h1>🌱 GrowMaster</h1>
      <p>{auth.loading ? "Preverjam zaščito aplikacije …" : setup ? "Pred prvo uporabo zaščiti podatke kmetije z enim skrbniškim geslom." : "Vnesi skrbniško geslo za dostop do podatkov kmetije."}</p>
    </section>
    {!auth.loading && <form className="auth-card" onSubmit={submit}>
      <div><p className="eyebrow">{setup ? "Prva nastavitev" : "Varna prijava"}</p><h2>{setup ? "Ustvari skrbniški dostop" : "Dobrodošel nazaj"}</h2></div>
      {setup && <label>Ime kmetije<input value={form.farm_name} onChange={(event) => setForm({ ...form, farm_name: event.target.value })} autoComplete="organization" maxLength="120" required autoFocus /></label>}
      {setup && <label>Ime uporabnika<input value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} autoComplete="name" maxLength="120" required /></label>}
      <label>Geslo<input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} autoComplete={setup ? "new-password" : "current-password"} minLength={setup ? 12 : 1} maxLength="256" required autoFocus={!setup} /></label>
      {setup && <label>Ponovi geslo<input type="password" value={form.confirmation} onChange={(event) => setForm({ ...form, confirmation: event.target.value })} autoComplete="new-password" minLength="12" maxLength="256" required /></label>}
      {setup && <p className="auth-hint">Uporabi vsaj 12 znakov ter vključuj črko in številko. Geslo ni vključeno v varnostne kopije.</p>}
      {setup && auth.demo_data_available && <label className="check-label setup-demo-choice"><input type="checkbox" checked={form.keep_demo_data} onChange={(event) => setForm({ ...form, keep_demo_data: event.target.checked })} /> Ohrani šest vzorčnih gredic in začetna opravila za preizkus</label>}
      {error && <div className="message error">⚠ {error}</div>}
      <button className="primary-button" type="submit">{setup ? "ZAŠČITI IN NADALJUJ" : "PRIJAVA"}</button>
      {!setup && <p className="auth-hint">Prijava velja {auth.session_days || 30} dni na tej napravi ali do odjave.</p>}
      {changeServer && <div className="server-choice"><small>Povezano: {serverUrl}</small><button type="button" className="text-button" onClick={changeServer}>IZBERI DRUG STREŽNIK</button></div>}
    </form>}
  </main>;
}

function SettingsView({ profile, setProfile, saveProfile, account, accountForm, setAccountForm, passwordForm, setPasswordForm, updateAccount, changePassword }) {
  return <>
    <form className="panel farm-profile-form" onSubmit={saveProfile}>
      <div className="section-heading"><div><p className="eyebrow">Identiteta kmetije</p><h2>Profil in podatki za dokumente</h2><p className="muted">Ime se prikaže v GrowMasterju in uporabi kot naziv prodajalca na vseh novih dokumentih. Že izdani računi ostanejo nespremenjeni.</p></div><span className={`profile-readiness ${profile.business_documents_ready ? "ready" : "incomplete"}`}>{profile.business_documents_ready ? "PRIPRAVLJENO ZA RAČUNE" : "DOPOLNI ZA POSLOVNE RAČUNE"}</span></div>
      <div className="farm-profile-fields">
        <label>Naziv kmetije<input value={profile.farm_name || ""} onChange={(event) => setProfile({ ...profile, farm_name: event.target.value })} maxLength="120" required /></label>
        <label>Davčna številka<input value={profile.seller_tax_number || ""} onChange={(event) => setProfile({ ...profile, seller_tax_number: event.target.value || null })} maxLength="30" /></label>
        <label className="wide">Naslov prodajalca<textarea value={profile.seller_address || ""} onChange={(event) => setProfile({ ...profile, seller_address: event.target.value })} placeholder="Potreben za račune poslovnim kupcem" /></label>
        <label>IBAN<input value={profile.seller_iban || ""} onChange={(event) => setProfile({ ...profile, seller_iban: event.target.value || null })} /></label>
        <label>Matična številka<input value={profile.seller_registration_number || ""} onChange={(event) => setProfile({ ...profile, seller_registration_number: event.target.value || null })} /></label>
        <label className="wide">Davčna opomba<input value={profile.vat_note || ""} onChange={(event) => setProfile({ ...profile, vat_note: event.target.value || null })} placeholder="Npr. klavzula glede DDV" /></label>
        <label>Poslovni prostor<input value={profile.business_premise_code || "GM"} onChange={(event) => setProfile({ ...profile, business_premise_code: event.target.value })} required /></label>
        <label>Naprava<input value={profile.device_code || "01"} onChange={(event) => setProfile({ ...profile, device_code: event.target.value })} required /></label>
        <label>Privzeti rok plačila (dni)<input type="number" min="0" max="365" value={profile.default_due_days ?? 14} onChange={(event) => setProfile({ ...profile, default_due_days: Number(event.target.value) })} required /></label>
        <label className="check-label wide"><input type="checkbox" checked={profile.basic_agriculture_invoice_exemption ?? true} onChange={(event) => setProfile({ ...profile, basic_agriculture_invoice_exemption: event.target.checked })} /> Za neposredno prodajo končnim kupcem uporabljam izjemo osnovne kmetijske dejavnosti; poslovni kupec še vedno dobi račun.</label>
      </div>
      <button className="primary-button" type="submit">SHRANI PROFIL KMETIJE</button>
    </form>
    <section className="panel settings-heading">
      <div><p className="eyebrow">Dostop do aplikacije</p><h2>Nastavitve uporabnika</h2><p className="muted">Spremembe so zaščitene s trenutnim geslom. Geslo in prijavne seje ostanejo ločeni od poslovnih varnostnih kopij.</p></div>
      <span className="data-safe-badge">✓ ZAŠČITENO</span>
    </section>
    <section className="metric-grid settings-metrics">
      <article className="metric-card"><span>Uporabnik</span><strong>{account.display_name || "—"}</strong><small>edini skrbniški dostop</small></article>
      <article className="metric-card"><span>Aktivne prijave</span><strong>{account.active_sessions || 0}</strong><small>največ 10 naprav oziroma brskalnikov</small></article>
      <article className="metric-card"><span>Veljavnost prijave</span><strong>{account.session_days || 30} dni</strong><small>ali do ročne odjave</small></article>
    </section>
    <section className="settings-grid">
      <form className="panel settings-form" onSubmit={updateAccount}>
        <div><p className="eyebrow">Prikaz v aplikaciji</p><h2>Spremeni ime</h2></div>
        <label>Ime uporabnika<input value={accountForm.display_name} onChange={(event) => setAccountForm({ ...accountForm, display_name: event.target.value })} maxLength="120" autoComplete="name" required /></label>
        <label>Trenutno geslo<input type="password" value={accountForm.current_password} onChange={(event) => setAccountForm({ ...accountForm, current_password: event.target.value })} autoComplete="current-password" required /></label>
        <button className="primary-button" type="submit">SHRANI IME</button>
      </form>
      <form className="panel settings-form" onSubmit={changePassword}>
        <div><p className="eyebrow">Varnost računa</p><h2>Spremeni geslo</h2></div>
        <label>Trenutno geslo<input type="password" value={passwordForm.current_password} onChange={(event) => setPasswordForm({ ...passwordForm, current_password: event.target.value })} autoComplete="current-password" required /></label>
        <label>Novo geslo<input type="password" value={passwordForm.new_password} onChange={(event) => setPasswordForm({ ...passwordForm, new_password: event.target.value })} autoComplete="new-password" minLength="12" maxLength="256" required /></label>
        <label>Ponovi novo geslo<input type="password" value={passwordForm.confirmation} onChange={(event) => setPasswordForm({ ...passwordForm, confirmation: event.target.value })} autoComplete="new-password" minLength="12" maxLength="256" required /></label>
        <p className="auth-hint">Vsaj 12 znakov, črka in številka. Po spremembi bodo vse druge naprave samodejno odjavljene.</p>
        <button className="danger-button" type="submit">SPREMENI GESLO</button>
      </form>
    </section>
    <p className="security-note">Če geslo pozabiš, ga zaradi varnosti ni mogoče pridobiti iz baze ali varnostne kopije. Pred uporabo pravih podatkov ga shrani v zaupanja vreden upravljalnik gesel.</p>
  </>;
}

registerGrowMasterServiceWorker();
createRoot(document.getElementById("root")).render(<React.StrictMode><App /></React.StrictMode>);
