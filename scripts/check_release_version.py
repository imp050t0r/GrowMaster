"""Ensure every user-visible GrowMaster version stays in sync."""

from pathlib import Path
import os
import re


ROOT = Path(__file__).resolve().parents[1]
VERSION_SOURCES = {
    "backend": (ROOT / "backend/app/server.py", r'APP_VERSION\s*=\s*"([^"]+)"'),
    "frontend": (ROOT / "frontend/src/version.js", r'APP_VERSION\s*=\s*"([^"]+)"'),
    "installer": (ROOT / "installer/GrowMaster.iss", r'MyAppVersion\s+"([^"]+)"'),
}


def read_versions() -> dict[str, str]:
    versions = {}
    for name, (path, pattern) in VERSION_SOURCES.items():
        match = re.search(pattern, path.read_text(encoding="utf-8"))
        if match is None:
            raise SystemExit(f"Could not read the application version from {path}")
        versions[name] = match.group(1)
    return versions


def main() -> None:
    versions = read_versions()
    if len(set(versions.values())) != 1:
        detail = ", ".join(f"{name}={version}" for name, version in versions.items())
        raise SystemExit(f"GrowMaster versions are not aligned: {detail}")

    version = next(iter(versions.values()))
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        tag_version = os.environ.get("GITHUB_REF_NAME", "").removeprefix("v")
        if tag_version != version:
            raise SystemExit(
                f"Tag v{tag_version} does not match application version {version}."
            )
    print(f"GrowMaster {version}: all versions are aligned.")


if __name__ == "__main__":
    main()
