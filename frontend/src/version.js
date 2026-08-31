import "./backupCenter";
import "./seedSupplierSearch";

export const APP_VERSION = "1.24.15";

// Release 1.24.15 adds the internet-connected Seed Supplier Search workflow:
// Plant DB -> live supplier offers -> Nabava -> PREVZEM SEMENA -> Seed Inventory.
// Physical seed stock is increased only after a confirmed receipt.
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
