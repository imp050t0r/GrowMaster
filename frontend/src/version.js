import "./backupCenter";

export const APP_VERSION = "1.24.14";

// Release 1.24.14 packages the GrowMaster offline-first POS for tablet/mobile
// together with the current Windows and Android application builds. The POS
// uses the same GrowMaster inventory and retail-sales data so stock, cash flow
// and analyses stay in one system after synchronization.
function syncReadinessAppVersion() {
  const expected = `Različica ${APP_VERSION}`;
  document.querySelectorAll(".readiness-panel .section-heading > span").forEach((node) => {
    if (node.textContent?.trim().startsWith("Različica") && node.textContent !== expected) {
      node.textContent = expected;
    }
  });
}

if (typeof document !== "undefined") {
  const start = () => {
    syncReadinessAppVersion();
    const observer = new MutationObserver(syncReadinessAppVersion);
    observer.observe(document.documentElement, { childList: true, subtree: true });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
}
