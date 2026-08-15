"""Build the PWA, native and Windows icon sizes from the approved carrot art."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "branding" / "growmaster-carrot.png"
PWA = ROOT / "frontend" / "public" / "icons"
INSTALLER = ROOT / "installer" / "assets"


def fitted_canvas(size: int, *, background=None, coverage: float = 0.82) -> Image.Image:
    source = Image.open(SOURCE).convert("RGBA")
    box = source.getchannel("A").getbbox()
    if box is None:
        raise RuntimeError("Branding source has no visible pixels.")
    subject = source.crop(box)
    target = round(size * coverage)
    subject.thumbnail((target, target), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), background or (0, 0, 0, 0))
    canvas.alpha_composite(subject, ((size - subject.width) // 2, (size - subject.height) // 2))
    return canvas


PWA.mkdir(parents=True, exist_ok=True)
INSTALLER.mkdir(parents=True, exist_ok=True)
for size in (192, 512):
    fitted_canvas(size).save(PWA / f"growmaster-{size}.png", optimize=True)
fitted_canvas(180).save(PWA / "apple-touch-icon.png", optimize=True)
fitted_canvas(512, background=(20, 60, 47, 255), coverage=0.68).save(
    PWA / "growmaster-maskable-512.png", optimize=True
)

windows_icon = fitted_canvas(512)
windows_icon.save(
    INSTALLER / "GrowMaster.ico",
    format="ICO",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
