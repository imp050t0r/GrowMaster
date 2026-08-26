"""Synchronize generated Android/iOS package versions with GrowMaster APP_VERSION.

Run after `cap add` / `cap sync`, because the native projects are generated during CI.
The canonical version remains frontend/src/version.js.
"""

from __future__ import annotations

from pathlib import Path
import plistlib
import re

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
VERSION_FILE = FRONTEND / "src" / "version.js"


def read_version() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', text)
    if not match:
        raise SystemExit(f"Could not read APP_VERSION from {VERSION_FILE}")
    return match.group(1)


def android_version_code(version: str) -> int:
    major, minor, patch = (int(part) for part in version.split("."))
    if minor >= 1000 or patch >= 1000:
        raise SystemExit("Android versionCode mapping requires minor/patch < 1000")
    return major * 1_000_000 + minor * 1_000 + patch


def sync_android(version: str) -> None:
    gradle = FRONTEND / "android" / "app" / "build.gradle"
    if not gradle.exists():
        return
    text = gradle.read_text(encoding="utf-8")
    code = android_version_code(version)
    text, code_count = re.subn(r"(?m)^(\s*)versionCode\s+\d+\s*$", rf"\g<1>versionCode {code}", text)
    text, name_count = re.subn(r'(?m)^(\s*)versionName\s+"[^"]*"\s*$', rf'\g<1>versionName "{version}"', text)
    if code_count != 1 or name_count != 1:
        raise SystemExit("Could not update Android versionCode/versionName exactly once")
    gradle.write_text(text, encoding="utf-8")
    print(f"Android: versionName={version}, versionCode={code}")


def sync_ios(version: str) -> None:
    plist_path = FRONTEND / "ios" / "App" / "App" / "Info.plist"
    if not plist_path.exists():
        return
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    plist["CFBundleShortVersionString"] = version
    plist["CFBundleVersion"] = str(android_version_code(version))
    with plist_path.open("wb") as handle:
        plistlib.dump(plist, handle)
    print(f"iOS: CFBundleShortVersionString={version}")


def main() -> None:
    version = read_version()
    sync_android(version)
    sync_ios(version)


if __name__ == "__main__":
    main()
