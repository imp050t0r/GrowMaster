import "./backupCenter";

export const APP_VERSION = "1.24.13";

// Release 1.24.13 packages the latest GrowMaster application changes, including
// structured baby-leaf recipes and their Seed Inventory workflow, into the
// Windows and Android builds. The production-readiness endpoint reports the
// server version; native UI must show the installed app/APK version.
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
