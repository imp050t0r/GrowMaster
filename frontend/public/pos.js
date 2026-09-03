(() => {
  const INVENTORY_KEY = "growmaster:pos:inventory";
  const QUEUE_KEY = "growmaster:pos:queue";
  const SALES_KEY = "growmaster:pos:recent-sales";
  const SERVER_URL_KEY = "growmaster:server-url";
  const SESSION_TOKEN_KEY = "growmaster:mobile-session";
  const DEVICE_ID_KEY = "growmaster:pos:device-id";
  const deviceId = localStorage.getItem(DEVICE_ID_KEY) || `device-${uuid()}`;
  localStorage.setItem(DEVICE_ID_KEY, deviceId);

  const state = {
    inventory: readJson(INVENTORY_KEY, []),
    queue: readJson(QUEUE_KEY, []),
    recentSales: readJson(SALES_KEY, []),
    cart: [],
    selectedHarvestId: null,
    selectedReturnItemId: null,
    mode: "sale",
    syncing: false,
  };

  const els = {
    connection: document.getElementById("connection"), syncState: document.getElementById("syncState"),
    inventoryMeta: document.getElementById("inventoryMeta"), products: document.getElementById("products"),
    search: document.getElementById("search"), refresh: document.getElementById("refresh"),
    cart: document.getElementById("cart"), total: document.getElementById("total"), clearCart: document.getElementById("clearCart"),
    quantity: document.getElementById("quantity"), addQuantity: document.getElementById("addQuantity"),
    payCash: document.getElementById("payCash"), payCard: document.getElementById("payCard"), message: document.getElementById("message"),
    saleMode: document.getElementById("saleMode"), writeOffMode: document.getElementById("writeOffMode"),
    returnMode: document.getElementById("returnMode"),
    cartTitle: document.getElementById("cartTitle"), writeOffReasonBox: document.getElementById("writeOffReasonBox"),
    writeOffReason: document.getElementById("writeOffReason"), confirmWriteOff: document.getElementById("confirmWriteOff"),
    returnOptions: document.getElementById("returnOptions"), returnReason: document.getElementById("returnReason"),
    returnToStock: document.getElementById("returnToStock"), confirmReturn: document.getElementById("confirmReturn"),
    dayCloseOpen: document.getElementById("dayCloseOpen"), dayDialog: document.getElementById("dayDialog"), dayCloseX: document.getElementById("dayCloseX"),
    openingCash: document.getElementById("openingCash"), countedCash: document.getElementById("countedCash"), dayNotes: document.getElementById("dayNotes"),
    daySummary: document.getElementById("daySummary"), dayRefresh: document.getElementById("dayRefresh"), dayConfirm: document.getElementById("dayConfirm"),
    historyOpen: document.getElementById("historyOpen"), unitsOpen: document.getElementById("unitsOpen"), stocktakeOpen: document.getElementById("stocktakeOpen"), pickupOpen: document.getElementById("pickupOpen"),
    workDialog: document.getElementById("workDialog"), workTitle: document.getElementById("workTitle"), workBody: document.getElementById("workBody"), workClose: document.getElementById("workClose"),
  };

  function readJson(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key) || "") || fallback; } catch { return fallback; }
  }
  function saveJson(key, value) { localStorage.setItem(key, JSON.stringify(value)); }
  function isNative() { return Boolean(window.Capacitor?.isNativePlatform?.() || ["capacitor:", "ionic:"].includes(location.protocol)); }
  function apiBase() { return isNative() ? (localStorage.getItem(SERVER_URL_KEY) || "") : ""; }
  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (isNative()) {
      headers.set("X-GrowMaster-Client", "mobile");
      const token = localStorage.getItem(SESSION_TOKEN_KEY);
      if (token) headers.set("Authorization", `Bearer ${token}`);
    }
    const response = await fetch(`${apiBase()}${path}`, { ...options, headers, credentials: isNative() ? "omit" : "include" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail;
      throw new Error(typeof detail === "string" ? detail : detail?.message || "Povezava z GrowMasterjem ni uspela.");
    }
    return data;
  }
  function money(value) { return `${Number(value || 0).toFixed(2).replace(".", ",")} €`; }
  function qty(value) { return `${Number(value || 0).toFixed(2).replace(".", ",")} kg`; }
  function uuid() { return globalThis.crypto?.randomUUID?.() || `pos-${Date.now()}-${Math.random().toString(16).slice(2)}`; }
  function showMessage(text, type = "") {
    els.message.textContent = text; els.message.className = `message ${type}`; els.message.hidden = !text;
    if (text) setTimeout(() => { if (els.message.textContent === text) els.message.hidden = true; }, 4500);
  }
  function localDate() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`; }

  function availableFor(item) {
    const pending = state.queue.reduce((sum, event) => sum + event.items.filter(x => x.harvest_id === item.harvest_id).reduce((s, x) => s + x.quantity_kg, 0), 0);
    const cart = state.cart.filter(x => x.harvest_id === item.harvest_id).reduce((sum, x) => sum + x.quantity_kg, 0);
    return Math.max(0, Number(item.available_kg || 0) - pending - cart);
  }

  function renderProducts() {
    const term = els.search.value.trim().toLowerCase();
    if (state.mode === "return") return renderReturnProducts(term);
    const items = state.inventory.filter(item => {
      const available = availableFor(item);
      const price = Number(item.suggested_price_per_kg_eur || 0);
      const matches = `${item.crop} ${item.variety || ""}`.toLowerCase().includes(term);
      return available > 0 && (state.mode === "write_off" || price > 0) && matches;
    });
    els.products.innerHTML = "";
    for (const item of items) {
      if (state.mode === "sale") {
        const kgButton = productButton(item, `${item.crop}${item.variety ? ` · ${item.variety}` : ""}`, `${qty(availableFor(item))} · TEHTANO`, null);
        els.products.appendChild(kgButton);
        for (const unit of item.sale_units || []) {
          if (availableFor(item) + 1e-6 < Number(unit.weight_kg)) continue;
          const button = productButton(item, `${item.crop} · ${unit.name}`, `${money(unit.price_eur)} · ${qty(unit.weight_kg)}`, unit);
          if (unit.button_color) button.style.borderTop = `8px solid ${unit.button_color}`;
          els.products.appendChild(button);
        }
        continue;
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className = `product-button${state.selectedHarvestId === item.harvest_id ? " selected" : ""}`;
      button.innerHTML = `<strong>${escapeHtml(item.crop)}${item.variety ? ` · ${escapeHtml(item.variety)}` : ""}</strong><span>${qty(availableFor(item))}</span>`;
      button.addEventListener("click", () => { state.selectedHarvestId = item.harvest_id; renderProducts(); });
      els.products.appendChild(button);
    }
    if (!items.length) els.products.innerHTML = '<p class="empty">Ni artiklov na zalogi.</p>';
    els.inventoryMeta.textContent = `${items.length} artiklov na zalogi · ${state.queue.length} nesinhroniziranih dogodkov`;
  }

  function productButton(item, title, subtitle, unit) {
    const button = document.createElement("button"); button.type = "button"; button.className = "product-button";
    button.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(subtitle)}</span>`;
    button.addEventListener("click", () => {
      state.selectedHarvestId = item.harvest_id;
      if (unit) addPackagedUnit(item, unit); else renderProducts();
    });
    return button;
  }

  function addPackagedUnit(item, unit) {
    const weight = Number(unit.weight_kg), price = Number(unit.price_eur);
    if (weight > availableFor(item)) return showMessage(`Na voljo je še ${qty(availableFor(item))}.`, "error");
    const key = `${item.harvest_id}:${unit.id}`;
    const existing = state.cart.find(x => x.cart_key === key);
    if (existing) { existing.unit_count += 1; existing.quantity_kg = Number((existing.unit_count * weight).toFixed(3)); }
    else state.cart.push({ cart_key: key, harvest_id: item.harvest_id, crop: item.crop, variety: `${item.variety} · ${unit.name}`, quality: item.quality, quantity_kg: weight, price_per_kg_eur: price / weight, sale_unit: unit.unit_type, unit_count: 1, unit_weight_kg: weight });
    renderAll();
  }

  function returnableFor(item) {
    const pending = state.queue.reduce((sum, event) => {
      if (event.type !== "return") return sum;
      return sum + event.items.filter(x => x.retail_sale_item_id === item.id).reduce((s, x) => s + x.quantity_kg, 0);
    }, 0);
    const cart = state.cart.find(x => x.retail_sale_item_id === item.id)?.quantity_kg || 0;
    return Math.max(0, Number(item.returnable_kg || 0) - pending - cart);
  }

  function returnItems() {
    const selectedSaleId = state.cart[0]?.retail_sale_id;
    return state.recentSales.flatMap(sale => sale.items.map(item => ({ ...item, retail_sale_id: sale.id, sale_number: sale.number, sale_date: sale.sale_date, payment_method: sale.payment_method })))
      .filter(item => !selectedSaleId || item.retail_sale_id === selectedSaleId);
  }

  function renderReturnProducts(term) {
    const items = returnItems().filter(item => returnableFor(item) > 0 && `${item.crop} ${item.variety || ""} ${item.sale_number}`.toLowerCase().includes(term));
    els.products.innerHTML = "";
    for (const item of items) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `product-button${state.selectedReturnItemId === item.id ? " selected" : ""}`;
      button.innerHTML = `<strong>${escapeHtml(item.crop)}${item.variety ? ` · ${escapeHtml(item.variety)}` : ""}</strong><span>${escapeHtml(item.sale_number)} · ${escapeHtml(item.sale_date)}</span><b>Vračljivo ${qty(returnableFor(item))}</b>`;
      button.addEventListener("click", () => { state.selectedReturnItemId = item.id; renderProducts(); });
      els.products.appendChild(button);
    }
    if (!items.length) els.products.innerHTML = '<p class="empty">Ni prodajnih postavk za vračilo.</p>';
    els.inventoryMeta.textContent = `${items.length} postavk za vračilo · ${state.queue.length} nesinhroniziranih dogodkov`;
  }

  function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c])); }

  function addSelectedQuantity(amount) {
    if (state.mode === "return") return addReturnQuantity(amount);
    const item = state.inventory.find(x => x.harvest_id === state.selectedHarvestId);
    if (!item) return showMessage("Najprej izberi artikel.", "error");
    const quantity = Number(amount);
    if (!Number.isFinite(quantity) || quantity <= 0) return showMessage("Vnesi veljavno količino.", "error");
    const existing = state.cart.find(x => x.harvest_id === item.harvest_id && (x.sale_unit || "kg") === "kg");
    const already = existing?.quantity_kg || 0;
    if (quantity > availableFor(item)) return showMessage(`Na voljo je še ${qty(availableFor(item))}.`, "error");
    if (existing) existing.quantity_kg = Number((already + quantity).toFixed(3));
    else state.cart.push({ cart_key: `${item.harvest_id}:kg`, harvest_id: item.harvest_id, crop: item.crop, variety: item.variety, quality: item.quality, quantity_kg: quantity, price_per_kg_eur: Number(item.suggested_price_per_kg_eur || 0), sale_unit: "kg" });
    els.quantity.value = ""; renderAll();
  }

  function addReturnQuantity(amount) {
    const item = returnItems().find(x => x.id === state.selectedReturnItemId);
    if (!item) return showMessage("Najprej izberi prodajno postavko.", "error");
    const quantity = Number(amount);
    if (!Number.isFinite(quantity) || quantity <= 0) return showMessage("Vnesi veljavno količino.", "error");
    const existing = state.cart.find(x => x.retail_sale_item_id === item.id);
    if (quantity > returnableFor(item)) return showMessage(`Vrniti je mogoče še ${qty(returnableFor(item))}.`, "error");
    if (existing) existing.quantity_kg = Number((existing.quantity_kg + quantity).toFixed(3));
    else state.cart.push({ retail_sale_item_id: item.id, retail_sale_id: item.retail_sale_id, crop: item.crop, variety: item.variety, quantity_kg: quantity, price_per_kg_eur: item.price_per_kg_eur, payment_method: item.payment_method });
    els.quantity.value = ""; renderAll();
  }

  function renderCart() {
    els.cart.innerHTML = "";
    if (!state.cart.length) els.cart.innerHTML = '<p class="empty">Izberi artikel.</p>';
    for (const item of state.cart) {
      const row = document.createElement("div"); row.className = "cart-row";
      const lineTotal = item.quantity_kg * item.price_per_kg_eur;
      row.innerHTML = state.mode === "sale"
        ? `<div><strong>${escapeHtml(item.crop)}${item.variety ? ` · ${escapeHtml(item.variety)}` : ""}</strong><small>${qty(item.quantity_kg)} × ${money(item.price_per_kg_eur)}/kg</small></div><b>${money(lineTotal)}</b>`
        : state.mode === "return"
        ? `<div><strong>${escapeHtml(item.crop)}${item.variety ? ` · ${escapeHtml(item.variety)}` : ""}</strong><small>${qty(item.quantity_kg)} × ${money(item.price_per_kg_eur)}/kg</small></div><b>− ${money(lineTotal)}</b>`
        : `<div><strong>${escapeHtml(item.crop)}${item.variety ? ` · ${escapeHtml(item.variety)}` : ""}</strong><small>${qty(item.quantity_kg)}</small></div><b>ODPIS</b>`;
      const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "✕"; remove.setAttribute("aria-label", "Odstrani");
      remove.addEventListener("click", () => { state.cart = state.cart.filter(x => state.mode === "return" ? x.retail_sale_item_id !== item.retail_sale_item_id : x.harvest_id !== item.harvest_id); renderAll(); });
      row.appendChild(remove); els.cart.appendChild(row);
    }
    const total = state.cart.reduce((sum, x) => sum + x.quantity_kg * x.price_per_kg_eur, 0);
    els.total.textContent = money(total);
    els.payCash.disabled = els.payCard.disabled = state.cart.length === 0;
    els.confirmWriteOff.disabled = state.cart.length === 0;
    els.confirmReturn.disabled = state.cart.length === 0;
    const writingOff = state.mode === "write_off";
    const returning = state.mode === "return";
    document.querySelector(".payment-buttons").hidden = writingOff || returning;
    document.querySelector(".total").hidden = writingOff;
    els.writeOffReasonBox.hidden = !writingOff;
    els.confirmWriteOff.hidden = !writingOff;
    els.returnOptions.hidden = !returning;
    els.confirmReturn.hidden = !returning;
    els.cartTitle.textContent = writingOff ? "Odpis zaloge" : returning ? "Vračilo" : "Račun";
    els.saleMode.classList.toggle("mode-active", state.mode === "sale");
    els.writeOffMode.classList.toggle("mode-active", writingOff);
    els.returnMode.classList.toggle("mode-active", returning);
  }

  function renderStatus() {
    const online = navigator.onLine;
    els.connection.textContent = online ? "● POVEZANO" : "● BREZ POVEZAVE";
    els.connection.className = `pill ${online ? "online" : "offline"}`;
    els.syncState.textContent = state.syncing ? "sinhroniziram…" : `${state.queue.length} čaka`;
  }
  function renderAll() { renderProducts(); renderCart(); renderStatus(); }

  async function refreshInventory() {
    if (!navigator.onLine) { renderAll(); return; }
    try {
      state.inventory = await api("/api/inventory");
      state.recentSales = await api("/api/retail-sales");
      saveJson(INVENTORY_KEY, state.inventory);
      saveJson(SALES_KEY, state.recentSales);
      renderAll();
    } catch (error) { showMessage(error.message, "error"); }
  }

  function buildSale(paymentMethod) {
    const d = new Date();
    const saleDate = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
    return {
      id: uuid(), created_at: d.toISOString(), sale_date: saleDate, payment_method: paymentMethod,
      device_id: deviceId,
      items: state.cart.map(({ harvest_id, quantity_kg, price_per_kg_eur, sale_unit = "kg", unit_count = null, unit_weight_kg = null }) => ({ harvest_id, quantity_kg, price_per_kg_eur, sale_unit, unit_count, unit_weight_kg })),
    };
  }

  async function checkout(paymentMethod) {
    if (!state.cart.length) return;
    const sale = buildSale(paymentMethod);
    state.queue.push(sale); saveJson(QUEUE_KEY, state.queue);
    state.cart = []; state.selectedHarvestId = null; renderAll();
    showMessage(paymentMethod === "cash" ? "Gotovinska prodaja shranjena." : "Kartična prodaja shranjena.", "success");
    if (navigator.onLine) await syncQueue();
  }

  async function confirmWriteOff() {
    if (!state.cart.length) return;
    const d = new Date();
    const writeOff = {
      type: "write_off", id: uuid(), created_at: d.toISOString(),
      write_off_date: `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`,
      reason: els.writeOffReason.value,
      items: state.cart.map(({ harvest_id, quantity_kg }) => ({ harvest_id, quantity_kg })),
    };
    state.queue.push(writeOff); saveJson(QUEUE_KEY, state.queue);
    state.cart = []; state.selectedHarvestId = null; renderAll();
    showMessage("Odpis je shranjen in čaka na sinhronizacijo zaloge.", "success");
    if (navigator.onLine) await syncQueue();
  }

  async function confirmReturn() {
    if (!state.cart.length) return;
    const d = new Date();
    const retailReturn = {
      type: "return", id: uuid(), created_at: d.toISOString(),
      return_date: `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`,
      reason: els.returnReason.value,
      items: state.cart.map(({ retail_sale_item_id, quantity_kg }) => ({ retail_sale_item_id, quantity_kg, return_to_stock: els.returnToStock.checked })),
    };
    state.queue.push(retailReturn); saveJson(QUEUE_KEY, state.queue);
    state.cart = []; state.selectedReturnItemId = null; renderAll();
    showMessage("Vračilo je shranjeno in čaka na sinhronizacijo.", "success");
    if (navigator.onLine) await syncQueue();
  }

  function setMode(mode) {
    if (state.mode === mode) return;
    state.mode = mode; state.cart = []; state.selectedHarvestId = null; state.selectedReturnItemId = null; renderAll();
  }

  async function syncQueue() {
    if (state.syncing || !navigator.onLine || !state.queue.length) { renderStatus(); return; }
    state.syncing = true; renderStatus();
    try {
      while (state.queue.length && navigator.onLine) {
        const event = state.queue[0];
        if (event.type === "write_off") {
          await api("/api/inventory-write-offs", {
            method: "POST",
            body: JSON.stringify({ write_off_date: event.write_off_date, reason: event.reason, client_event_id: event.id, device_id: deviceId, notes: `POS:${event.id}`, items: event.items }),
          });
        } else if (event.type === "return") {
          await api("/api/retail-returns", {
            method: "POST",
            body: JSON.stringify({ return_date: event.return_date, reason: event.reason, client_event_id: event.id, device_id: deviceId, notes: `POS:${event.id}`, items: event.items }),
          });
        } else {
          await api("/api/retail-sales", {
            method: "POST",
            body: JSON.stringify({ sale_date: event.sale_date, payment_method: event.payment_method, customer_id: null, client_event_id: event.id, device_id: event.device_id || deviceId, notes: `POS:${event.id}`, items: event.items }),
          });
        }
        state.queue.shift(); saveJson(QUEUE_KEY, state.queue);
      }
      await refreshInventory();
      if (!state.queue.length) showMessage("Prodaja, denarni tok in zaloga so sinhronizirani z GrowMasterjem.", "success");
    } catch (error) {
      showMessage(`Sinhronizacija čaka: ${error.message}`, "error");
    } finally { state.syncing = false; renderAll(); }
  }

  function dayCard(label, value) { return `<div class="day-card"><span>${label}</span><strong>${value}</strong></div>`; }
  async function loadDayPreview() {
    if (!navigator.onLine) return showMessage("Zaključek dneva potrebuje povezavo z GrowMasterjem.", "error");
    await syncQueue();
    if (state.queue.length) return showMessage("Najprej sinhroniziraj vse čakajoče dogodke.", "error");
    try {
      const opening = Math.max(0, Number(els.openingCash.value || 0));
      const data = await api(`/api/day-closes/preview?business_date=${localDate()}&opening_cash_eur=${opening}`);
      els.daySummary.innerHTML = data.closed
        ? dayCard("Stanje", "DAN JE ZAKLJUČEN") + dayCard("Prešteta gotovina", money(data.counted_cash_eur)) + dayCard("Razlika", money(data.difference_eur)) + dayCard("Neto prejemki", money(data.net_receipts_eur))
        : dayCard("Gotovinska prodaja", money(data.cash_in_eur)) + dayCard("Kartična prodaja", money(data.card_in_eur)) + dayCard("Vračila gotovine", money(data.cash_refund_eur)) + dayCard("Vsa vračila", money(data.total_refund_eur)) + dayCard("Pričakovana gotovina", money(data.expected_cash_eur)) + dayCard("Neto prejemki", money(data.net_receipts_eur));
      els.dayConfirm.disabled = Boolean(data.closed);
      if (!data.closed && !els.countedCash.value) els.countedCash.value = Number(data.expected_cash_eur || 0).toFixed(2);
    } catch (error) { showMessage(error.message, "error"); }
  }
  async function openDayClose() {
    els.dayDialog.showModal();
    await loadDayPreview();
  }
  async function confirmDayClose() {
    const counted = Number(els.countedCash.value);
    if (!Number.isFinite(counted) || counted < 0) return showMessage("Vnesi prešteto gotovino.", "error");
    if (!navigator.onLine || state.queue.length) return showMessage("Pred zaključkom sinhroniziraj vse dogodke.", "error");
    try {
      const result = await api("/api/day-closes", { method: "POST", body: JSON.stringify({ business_date: localDate(), opening_cash_eur: Math.max(0, Number(els.openingCash.value || 0)), counted_cash_eur: counted, notes: els.dayNotes.value.trim() || null }) });
      els.dayDialog.close();
      showMessage(`Dan je zaključen. Razlika blagajne: ${money(result.difference_eur)}.`, result.difference_eur === 0 ? "success" : "");
    } catch (error) { showMessage(error.message, "error"); }
  }
  function openWork(title, html) { els.workTitle.textContent = title; els.workBody.innerHTML = html; els.workDialog.showModal(); }
  async function showHistory() {
    if (!navigator.onLine) return showMessage("Zgodovina potrebuje povezavo.", "error");
    const [sales, returns, writeOffs] = await Promise.all([api("/api/retail-sales"), api("/api/retail-returns"), api("/api/inventory-write-offs")]);
    const rows = [
      ...returns.map(x => ({ date:x.return_date, type:"VRAČILO", ref:x.sale_number, value:`− ${money(x.total_eur)}`, device:"POS" })),
      ...writeOffs.map(x => ({ date:x.write_off_date, type:"ODPIS", ref:`Žetev ${x.harvest_id}`, value:qty(x.quantity_kg), device:"POS" })),
    ].sort((a,b)=>String(b.date).localeCompare(String(a.date)));
    const saleCards = sales.map(x=>{ const returnable=x.items.filter(i=>i.returnable_kg>0); return `<div class="day-card"><span>${escapeHtml(x.sale_date)} · PRODAJA · ${escapeHtml(x.device_id || "računalnik")}</span><strong>${escapeHtml(x.number)} · ${money(x.total_eur)}</strong>${returnable.length && !x.invoice ? `<button data-void-sale="${x.id}" class="secondary">STORNO</button>`:""}</div>`; }).join("");
    openWork("Zgodovina POS", saleCards + rows.map(x=>`<div class="day-card"><span>${escapeHtml(x.date)} · ${x.type} · ${escapeHtml(x.device)}</span><strong>${escapeHtml(x.ref)} · ${x.value}</strong></div>`).join("") || '<p class="empty">Ni dogodkov.</p>');
    els.workBody.querySelectorAll("[data-void-sale]").forEach(button=>button.onclick=async()=>{ const sale=sales.find(x=>x.id===Number(button.dataset.voidSale)); await api("/api/retail-returns",{method:"POST",body:JSON.stringify({return_date:localDate(),reason:"other",notes:`STORNO ${sale.number}`,client_event_id:uuid(),device_id:deviceId,items:sale.items.filter(i=>i.returnable_kg>0).map(i=>({retail_sale_item_id:i.id,quantity_kg:i.returnable_kg,return_to_stock:true}))})}); els.workDialog.close(); await refreshInventory(); showMessage("Prodaja je stornirana; zaloga in denarni tok sta popravljena.","success"); });
  }
  async function showUnits() {
    const crops = [...new Map(state.inventory.filter(x=>x.available_kg>0).map(x=>[`${x.crop_id}:${x.quality}`,x])).values()];
    openWork("Prodajne enote", `<label class="day-input">Požeti artikel<select id="unitCrop">${crops.map(x=>`<option value="${x.crop_id}" data-quality="${x.quality}">${escapeHtml(x.crop)} · ${escapeHtml(x.quality)}</option>`).join("")}</select></label><label class="day-input">Ime gumba<input id="unitName" placeholder="Pakiranje 150 g ali šopek" /></label><label class="day-input">Vrsta<select id="unitType"><option value="package">Pakiranje</option><option value="bunch">Šopek</option><option value="piece">Kos</option></select></label><label class="day-input">Teža enote (kg)<input id="unitWeight" type="number" min="0.001" step="0.001" /></label><label class="day-input">Cena enote (€)<input id="unitPrice" type="number" min="0.01" step="0.01" /></label><button id="unitSave" class="pay primary">SHRANI VELIK GUMB</button>`);
    document.getElementById("unitSave").onclick = async()=>{ const select=document.getElementById("unitCrop"), option=select.selectedOptions[0]; await api("/api/product-units",{method:"POST",body:JSON.stringify({crop_id:Number(select.value),quality:option.dataset.quality,name:document.getElementById("unitName").value,unit_type:document.getElementById("unitType").value,weight_kg:Number(document.getElementById("unitWeight").value),price_eur:Number(document.getElementById("unitPrice").value)})}); els.workDialog.close(); await refreshInventory(); showMessage("Prodajni gumb je dodan.","success"); };
  }
  function showStocktake() {
    openWork("Inventura", state.inventory.filter(x=>x.available_kg>0).map(x=>`<div class="day-card"><span>${escapeHtml(x.crop)} · ${escapeHtml(x.variety)} · pričakovano ${qty(x.available_kg)}</span><div class="custom-qty"><div><input data-count-harvest="${x.harvest_id}" type="number" min="0" step="0.01" value="${x.available_kg}"/><button data-save-count="${x.harvest_id}">USKLADI</button></div></div></div>`).join(""));
    els.workBody.querySelectorAll("[data-save-count]").forEach(button=>button.onclick=async()=>{ const id=Number(button.dataset.saveCount), input=els.workBody.querySelector(`[data-count-harvest="${id}"]`); await api("/api/inventory-adjustments",{method:"POST",body:JSON.stringify({harvest_id:id,adjustment_date:localDate(),counted_kg:Number(input.value),reason:"stocktake",client_event_id:uuid(),device_id:deviceId})}); await refreshInventory(); button.textContent="SHRANJENO"; button.disabled=true; });
  }
  async function showPickups() {
    const orders=(await api("/api/orders")).filter(x=>x.status==="confirmed");
    openWork("Rezervacije za prevzem", orders.length ? orders.map(x=>`<div class="day-card"><span>${escapeHtml(x.customer)} · ${escapeHtml(x.delivery_date)}</span><strong>${money(x.total_eur)}</strong><div class="day-actions"><button data-pickup="${x.id}" data-method="cash">GOTOVINA</button><button data-pickup="${x.id}" data-method="card">KARTICA</button></div></div>`).join("") : '<p class="empty">Ni potrjenih rezervacij.</p>');
    els.workBody.querySelectorAll("[data-pickup]").forEach(button=>button.onclick=async()=>{ await api(`/api/orders/${button.dataset.pickup}/pos-fulfill`,{method:"POST",body:JSON.stringify({payment_method:button.dataset.method,client_event_id:uuid(),device_id:deviceId})}); els.workDialog.close(); await refreshInventory(); showMessage("Prevzem je zaključen in plačilo evidentirano.","success"); });
  }

  document.querySelectorAll("[data-qty]").forEach(button => button.addEventListener("click", () => addSelectedQuantity(button.dataset.qty)));
  els.addQuantity.addEventListener("click", () => addSelectedQuantity(els.quantity.value));
  els.quantity.addEventListener("keydown", event => { if (event.key === "Enter") addSelectedQuantity(els.quantity.value); });
  els.clearCart.addEventListener("click", () => { state.cart = []; renderAll(); });
  els.payCash.addEventListener("click", () => checkout("cash"));
  els.payCard.addEventListener("click", () => checkout("card"));
  els.confirmWriteOff.addEventListener("click", confirmWriteOff);
  els.confirmReturn.addEventListener("click", confirmReturn);
  els.saleMode.addEventListener("click", () => setMode("sale"));
  els.writeOffMode.addEventListener("click", () => setMode("write_off"));
  els.returnMode.addEventListener("click", () => setMode("return"));
  els.dayCloseOpen.addEventListener("click", openDayClose);
  els.dayCloseX.addEventListener("click", () => els.dayDialog.close());
  els.dayRefresh.addEventListener("click", loadDayPreview);
  els.dayConfirm.addEventListener("click", confirmDayClose);
  els.openingCash.addEventListener("change", loadDayPreview);
  els.historyOpen.addEventListener("click", showHistory);
  els.unitsOpen.addEventListener("click", showUnits);
  els.stocktakeOpen.addEventListener("click", showStocktake);
  els.pickupOpen.addEventListener("click", showPickups);
  els.workClose.addEventListener("click",()=>els.workDialog.close());
  els.search.addEventListener("input", renderProducts);
  els.refresh.addEventListener("click", async () => { await syncQueue(); await refreshInventory(); });
  window.addEventListener("online", async () => { renderStatus(); await syncQueue(); await refreshInventory(); });
  window.addEventListener("offline", renderStatus);

  renderAll();
  refreshInventory().then(syncQueue);
  setInterval(() => { if (navigator.onLine) syncQueue(); }, 15000);
})();
