import "./backupCenter";
import "./seedSupplierSearch";

export const APP_VERSION = "1.24.25";

// Release 1.24.25 adds traceable offline-capable POS inventory write-offs. Release 1.24.24 completes professional source coverage for every crop. Release 1.24.23 adds verified professional Indian gourd varieties. Release 1.24.22 adds a verified professional bitter-gourd/karela set and
// multilingual crop aliases. Release 1.24.21 adds the first verified ICAR-IIHR professional Indian crop
// batch. Release 1.24.20 uses verified product pages before generic web search and
// keeps the professional coriander supplier flow usable when search engines fail.
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
