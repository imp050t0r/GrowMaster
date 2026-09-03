(() => {
  const INVENTORY_KEY = "growmaster:pos:inventory";
  const QUEUE_KEY = "growmaster:pos:queue";
  const SERVER_URL_KEY = "growmaster:server-url";
  const SESSION_TOKEN_KEY = "growmaster:mobile-session";

  const state = {
    inventory: readJson(INVENTORY_KEY, []),
    queue: readJson(QUEUE_KEY, []),
    cart: [],
    selectedHarvestId: null,
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
    cartTitle: document.getElementById("cartTitle"), writeOffReasonBox: document.getElementById("writeOffReasonBox"),
    writeOffReason: document.getElementById("writeOffReason"), confirmWriteOff: document.getElementById("confirmWriteOff"),
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

  function availableFor(item) {
    const pending = state.queue.reduce((sum, event) => sum + event.items.filter(x => x.harvest_id === item.harvest_id).reduce((s, x) => s + x.quantity_kg, 0), 0);
    const cart = state.cart.find(x => x.harvest_id === item.harvest_id)?.quantity_kg || 0;
    return Math.max(0, Number(item.available_kg || 0) - pending - cart);
  }

  function renderProducts() {
    const term = els.search.value.trim().toLowerCase();
    const items = state.inventory.filter(item => {
      const available = availableFor(item);
      const price = Number(item.suggested_price_per_kg_eur || 0);
      const matches = `${item.crop} ${item.variety || ""}`.toLowerCase().includes(term);
      return available > 0 && (state.mode === "write_off" || price > 0) && matches;
    });
    els.products.innerHTML = "";
    for (const item of items) {
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

  function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c])); }

  function addSelectedQuantity(amount) {
    const item = state.inventory.find(x => x.harvest_id === state.selectedHarvestId);
    if (!item) return showMessage("Najprej izberi artikel.", "error");
    const quantity = Number(amount);
    if (!Number.isFinite(quantity) || quantity <= 0) return showMessage("Vnesi veljavno količino.", "error");
    const existing = state.cart.find(x => x.harvest_id === item.harvest_id);
    const already = existing?.quantity_kg || 0;
    if (quantity > availableFor(item)) return showMessage(`Na voljo je še ${qty(availableFor(item))}.`, "error");
    if (existing) existing.quantity_kg = Number((already + quantity).toFixed(3));
    else state.cart.push({ harvest_id: item.harvest_id, crop: item.crop, variety: item.variety, quality: item.quality, quantity_kg: quantity, price_per_kg_eur: Number(item.suggested_price_per_kg_eur || 0) });
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
        : `<div><strong>${escapeHtml(item.crop)}${item.variety ? ` · ${escapeHtml(item.variety)}` : ""}</strong><small>${qty(item.quantity_kg)}</small></div><b>ODPIS</b>`;
      const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "✕"; remove.setAttribute("aria-label", "Odstrani");
      remove.addEventListener("click", () => { state.cart = state.cart.filter(x => x.harvest_id !== item.harvest_id); renderAll(); });
      row.appendChild(remove); els.cart.appendChild(row);
    }
    const total = state.cart.reduce((sum, x) => sum + x.quantity_kg * x.price_per_kg_eur, 0);
    els.total.textContent = money(total);
    els.payCash.disabled = els.payCard.disabled = state.cart.length === 0;
    els.confirmWriteOff.disabled = state.cart.length === 0;
    const writingOff = state.mode === "write_off";
    document.querySelector(".payment-buttons").hidden = writingOff;
    document.querySelector(".total").hidden = writingOff;
    els.writeOffReasonBox.hidden = !writingOff;
    els.confirmWriteOff.hidden = !writingOff;
    els.cartTitle.textContent = writingOff ? "Odpis zaloge" : "Račun";
    els.saleMode.classList.toggle("mode-active", !writingOff);
    els.writeOffMode.classList.toggle("mode-active", writingOff);
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
      saveJson(INVENTORY_KEY, state.inventory);
      renderAll();
    } catch (error) { showMessage(error.message, "error"); }
  }

  function buildSale(paymentMethod) {
    const d = new Date();
    const saleDate = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
    return {
      id: uuid(), created_at: d.toISOString(), sale_date: saleDate, payment_method: paymentMethod,
      items: state.cart.map(({ harvest_id, quantity_kg, price_per_kg_eur }) => ({ harvest_id, quantity_kg, price_per_kg_eur })),
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

  function setMode(mode) {
    if (state.mode === mode) return;
    state.mode = mode; state.cart = []; state.selectedHarvestId = null; renderAll();
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
            body: JSON.stringify({ write_off_date: event.write_off_date, reason: event.reason, client_event_id: event.id, notes: `POS:${event.id}`, items: event.items }),
          });
        } else {
          await api("/api/retail-sales", {
            method: "POST",
            body: JSON.stringify({ sale_date: event.sale_date, payment_method: event.payment_method, customer_id: null, notes: `POS:${event.id}`, items: event.items }),
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

  document.querySelectorAll("[data-qty]").forEach(button => button.addEventListener("click", () => addSelectedQuantity(button.dataset.qty)));
  els.addQuantity.addEventListener("click", () => addSelectedQuantity(els.quantity.value));
  els.quantity.addEventListener("keydown", event => { if (event.key === "Enter") addSelectedQuantity(els.quantity.value); });
  els.clearCart.addEventListener("click", () => { state.cart = []; renderAll(); });
  els.payCash.addEventListener("click", () => checkout("cash"));
  els.payCard.addEventListener("click", () => checkout("card"));
  els.confirmWriteOff.addEventListener("click", confirmWriteOff);
  els.saleMode.addEventListener("click", () => setMode("sale"));
  els.writeOffMode.addEventListener("click", () => setMode("write_off"));
  els.search.addEventListener("input", renderProducts);
  els.refresh.addEventListener("click", async () => { await syncQueue(); await refreshInventory(); });
  window.addEventListener("online", async () => { renderStatus(); await syncQueue(); await refreshInventory(); });
  window.addEventListener("offline", renderStatus);

  renderAll();
  refreshInventory().then(syncQueue);
  setInterval(() => { if (navigator.onLine) syncQueue(); }, 15000);
})();
