const SERVER_URL_KEY = "growmaster:server-url";
const SESSION_TOKEN_KEY = "growmaster:mobile-session";

export const isNativeApp = Boolean(
  window.Capacitor?.isNativePlatform?.()
  || ["capacitor:", "ionic:"].includes(window.location.protocol),
);

export function normalizeServerUrl(value) {
  const trimmed = String(value || "").trim().replace(/\/+$/, "");
  if (!trimmed) return "";
  const parsed = new URL(trimmed);
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error("Naslov mora začeti z http:// ali https://.");
  }
  return parsed.origin + parsed.pathname.replace(/\/+$/, "");
}

export function configuredServerUrl() {
  if (isNativeApp) return localStorage.getItem(SERVER_URL_KEY) || "";
  return import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");
}

export function saveServerUrl(value) {
  const normalized = normalizeServerUrl(value);
  localStorage.setItem(SERVER_URL_KEY, normalized);
  return normalized;
}

export function forgetServer() {
  localStorage.removeItem(SERVER_URL_KEY);
  localStorage.removeItem(SESSION_TOKEN_KEY);
}

export function saveNativeSession(token) {
  if (!isNativeApp) return;
  if (token) localStorage.setItem(SESSION_TOKEN_KEY, token);
  else localStorage.removeItem(SESSION_TOKEN_KEY);
}

export function apiHref(path) {
  return `${configuredServerUrl()}${path}`;
}

export async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (isNativeApp) {
    headers.set("X-GrowMaster-Client", "mobile");
    const token = localStorage.getItem(SESSION_TOKEN_KEY);
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(apiHref(path), {
    ...options,
    headers,
    credentials: isNativeApp ? "omit" : "include",
  });
}

export async function apiRequest(path, options = {}) {
  const response = await apiFetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/auth/")) {
      saveNativeSession("");
      window.dispatchEvent(new Event("growmaster:unauthorized"));
    }
    const detail = data.detail;
    const validationMessage = Array.isArray(detail)
      ? detail.map(item => item?.msg).filter(Boolean).join(" ")
      : "";
    throw new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || validationMessage || "Zahteva ni uspela.",
    );
  }
  return data;
}

export async function testServerConnection(value) {
  const serverUrl = normalizeServerUrl(value);
  const response = await fetch(`${serverUrl}/api/health`, {
    headers: { "X-GrowMaster-Client": "mobile" },
  });
  if (!response.ok) throw new Error("GrowMaster na tem naslovu ni dosegljiv.");
  const data = await response.json();
  if (data.app !== "GrowMaster" || data.status !== "running") {
    throw new Error("Na naslovu ni prepoznan strežnik GrowMaster.");
  }
  return { serverUrl, version: data.version };
}

export function registerGrowMasterServiceWorker() {
  if (isNativeApp || !("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => undefined);
  });
}
