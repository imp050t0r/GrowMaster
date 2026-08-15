"""Replace generated Capacitor icons with the approved GrowMaster carrot."""

from pathlib import Path
import json

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "branding" / "growmaster-carrot.png"
FRONTEND = ROOT / "frontend"


def app_icon(size: int, *, coverage: float = 0.72, background=(20, 60, 47, 255)) -> Image.Image:
    source = Image.open(SOURCE).convert("RGBA")
    box = source.getchannel("A").getbbox()
    if box is None:
        raise RuntimeError("Branding source has no visible pixels.")
    subject = source.crop(box)
    target = round(size * coverage)
    subject.thumbnail((target, target), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), background)
    canvas.alpha_composite(subject, ((size - subject.width) // 2, (size - subject.height) // 2))
    return canvas


android_sizes = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}
android_res = FRONTEND / "android" / "app" / "src" / "main" / "res"
if android_res.exists():
    for folder, size in android_sizes.items():
        target = android_res / folder
        target.mkdir(parents=True, exist_ok=True)
        for name in ("ic_launcher.png", "ic_launcher_round.png"):
            app_icon(size).save(target / name, optimize=True)
        app_icon(round(size * 2.25), coverage=0.60, background=(0, 0, 0, 0)).save(
            target / "ic_launcher_foreground.png", optimize=True
        )
    values = android_res / "values"
    values.mkdir(parents=True, exist_ok=True)
    (values / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <color name="ic_launcher_background">#143C2F</color>\n'
        '</resources>\n',
        encoding="utf-8",
    )

ios_set = FRONTEND / "ios" / "App" / "App" / "Assets.xcassets" / "AppIcon.appiconset"
if ios_set.exists():
    ios_set.mkdir(parents=True, exist_ok=True)
    entries = []
    definitions = [
        ("iphone", "20x20", "2x", 40), ("iphone", "20x20", "3x", 60),
        ("iphone", "29x29", "2x", 58), ("iphone", "29x29", "3x", 87),
        ("iphone", "40x40", "2x", 80), ("iphone", "40x40", "3x", 120),
        ("iphone", "60x60", "2x", 120), ("iphone", "60x60", "3x", 180),
        ("ipad", "20x20", "1x", 20), ("ipad", "20x20", "2x", 40),
        ("ipad", "29x29", "1x", 29), ("ipad", "29x29", "2x", 58),
        ("ipad", "40x40", "1x", 40), ("ipad", "40x40", "2x", 80),
        ("ipad", "76x76", "1x", 76), ("ipad", "76x76", "2x", 152),
        ("ipad", "83.5x83.5", "2x", 167),
        ("ios-marketing", "1024x1024", "1x", 1024),
    ]
    for idiom, logical_size, scale, pixels in definitions:
        filename = f"AppIcon-{pixels}-{idiom}-{scale}.png"
        app_icon(pixels).convert("RGB").save(ios_set / filename, optimize=True)
        entries.append({"idiom": idiom, "size": logical_size, "scale": scale, "filename": filename})
    (ios_set / "Contents.json").write_text(
        json.dumps({"images": entries, "info": {"author": "xcode", "version": 1}}, indent=2),
        encoding="utf-8",
    )

info_plist = FRONTEND / "ios" / "App" / "App" / "Info.plist"
if info_plist.exists():
    import plistlib

    with info_plist.open("rb") as handle:
        plist = plistlib.load(handle)
    plist["NSLocalNetworkUsageDescription"] = "GrowMaster se poveže z zasebnim strežnikom tvoje kmetije v lokalnem omrežju."
    plist.setdefault("NSAppTransportSecurity", {})["NSAllowsLocalNetworking"] = True
    with info_plist.open("wb") as handle:
        plistlib.dump(plist, handle)
