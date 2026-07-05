from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LOGO_DIR = ROOT / "logo"
SOURCE = LOGO_DIR / "SciPlot.jpg"
PNG = LOGO_DIR / "SciPlot.png"
ICO = LOGO_DIR / "SciPlot.ico"
ICNS = LOGO_DIR / "SciPlot.icns"


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing icon source: {SOURCE}")

    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(SOURCE).convert("RGBA")
    size = min(image.size)
    left = (image.width - size) // 2
    top = (image.height - size) // 2
    image = image.crop((left, top, left + size, top + size)).resize((1024, 1024), Image.Resampling.LANCZOS)

    image.save(PNG)
    image.save(ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    try:
        image.save(ICNS, sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])
    except Exception:
        # Pillow's ICNS writer depends on platform/library support. The macOS
        # release workflow can still generate an .icns file with iconutil.
        pass

    print(PNG)
    print(ICO)
    if ICNS.exists():
        print(ICNS)


if __name__ == "__main__":
    main()
