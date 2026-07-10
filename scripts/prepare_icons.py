from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
LOGO_DIR = ROOT / "logo"
SOURCE = LOGO_DIR / "SciPlot.jpg"
PNG = LOGO_DIR / "SciPlot.png"
ICO = LOGO_DIR / "SciPlot.ico"
ICNS = LOGO_DIR / "SciPlot.icns"


def remove_white_background(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    color_pixels = []
    alpha_values = []
    data = rgba.get_flattened_data() if hasattr(rgba, "get_flattened_data") else rgba.getdata()
    for red, green, blue, alpha in data:
        white_distance = ((255 - red) ** 2 + (255 - green) ** 2 + (255 - blue) ** 2) ** 0.5
        if white_distance <= 24:
            new_alpha = 0
        elif white_distance >= 96:
            new_alpha = alpha
        else:
            new_alpha = int((white_distance - 24) / 72 * 255)
        if 0 < new_alpha < 255:
            coverage = new_alpha / 255
            red = int(max(0, min(255, (red - 255 * (1 - coverage)) / coverage)))
            green = int(max(0, min(255, (green - 255 * (1 - coverage)) / coverage)))
            blue = int(max(0, min(255, (blue - 255 * (1 - coverage)) / coverage)))
        color_pixels.append((red, green, blue, alpha))
        alpha_values.append(min(alpha, max(0, min(255, new_alpha))))
    rgba.putdata(color_pixels)
    alpha_mask = Image.new("L", rgba.size)
    alpha_mask.putdata(alpha_values)
    alpha_mask = alpha_mask.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(0.2))
    rgba.putalpha(alpha_mask)
    return rgba


def make_app_icon(logo: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((70, 70, 954, 954), fill="#102a55")
    draw.ellipse((88, 88, 936, 936), outline="#22d3ee", width=22)

    icon_logo = logo.copy()
    icon_logo = ImageEnhance.Brightness(icon_logo).enhance(1.18)
    icon_logo = ImageEnhance.Contrast(icon_logo).enhance(1.08)
    bbox = icon_logo.getbbox()
    if bbox:
        icon_logo = icon_logo.crop(bbox)
    icon_logo.thumbnail((730, 730), Image.Resampling.LANCZOS)
    x = (1024 - icon_logo.width) // 2
    y = (1024 - icon_logo.height) // 2
    canvas.alpha_composite(icon_logo, (x, y))
    return canvas


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing icon source: {SOURCE}")

    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(SOURCE).convert("RGBA")
    size = min(image.size)
    left = (image.width - size) // 2
    top = (image.height - size) // 2
    image = image.crop((left, top, left + size, top + size)).resize((1024, 1024), Image.Resampling.LANCZOS)
    transparent_logo = remove_white_background(image)
    app_icon = make_app_icon(transparent_logo)

    for generated in (PNG, ICO, ICNS):
        generated.unlink(missing_ok=True)
    transparent_logo.save(PNG)
    app_icon.save(ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    try:
        app_icon.save(ICNS, sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])
    except Exception as exc:
        raise RuntimeError("Unable to generate the macOS application icon.") from exc

    print(PNG)
    print(ICO)
    if ICNS.exists():
        print(ICNS)


if __name__ == "__main__":
    main()
