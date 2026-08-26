import "./backupCenter";

export const APP_VERSION = "1.24.11";

// Release 1.24.11 completes the Windows Backup Center with file-based restore.
// The production-readiness endpoint reports the server version. In the native
// app the user-visible "Različica" label must report the installed app/APK
// version instead, otherwise a phone on a new APK can appear to be outdated.
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
