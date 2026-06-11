"""Render the ShimaTTS shiba logo (mirroring assets/logo.svg) into:
  assets/icon.ico                      - launcher exe icon
  src/overlay/static/icon.ico          - runtime window/taskbar icon + favicon
  src/overlay/static/shiba-icon.png    - tray icon base (status dot composited at runtime)
Run with any Python that has Pillow.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).parent.parent
F = 5  # supersample: 200-unit SVG space -> 1000px canvas


def P(*pts):
    return [(x * F, y * F) for x, y in pts]


def B(x0, y0, x1, y1):
    return [x0 * F, y0 * F, x1 * F, y1 * F]


def render() -> Image.Image:
    img = Image.new("RGBA", (200 * F, 200 * F), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Background: approximate the radial gradient with concentric circles
    steps = 60
    for i in range(steps):
        t = i / (steps - 1)
        r = 95 * (1 - t) + 20 * t
        c = (
            int(0x0D + (0x2A - 0x0D) * t),
            int(0x0D + (0x14 - 0x0D) * t),
            int(0x1A + (0x58 - 0x1A) * t),
            255,
        )
        d.ellipse(B(100 - r, 100 - r, 100 + r, 100 + r), fill=c)

    # Ears
    d.polygon(P((65, 84), (50, 50), (88, 78)), fill="#E07B2A")
    d.polygon(P((67, 80), (57, 57), (84, 76)), fill="#C9472E")
    d.polygon(P((135, 84), (150, 50), (112, 78)), fill="#E07B2A")
    d.polygon(P((133, 80), (143, 57), (116, 76)), fill="#C9472E")

    # Head + face
    d.ellipse(B(47, 65, 153, 163), fill="#E07B2A")
    d.ellipse(B(61, 87, 139, 155), fill="#FBE9CA")

    # Blush (translucent layer)
    blush = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(blush)
    bd.ellipse(B(57, 110, 81, 128), fill=(255, 110, 180, 95))
    bd.ellipse(B(119, 110, 143, 128), fill=(255, 110, 180, 95))
    img = Image.alpha_composite(img, blush)
    d = ImageDraw.Draw(img)

    # Eyes
    d.ellipse(B(74.5, 98.5, 91.5, 115.5), fill="#1a0c04")
    d.ellipse(B(108.5, 98.5, 125.5, 115.5), fill="#1a0c04")
    d.ellipse(B(83.2, 100.7, 88.8, 106.3), fill=(255, 255, 255, 230))
    d.ellipse(B(117.2, 100.7, 122.8, 106.3), fill=(255, 255, 255, 230))

    # Nose + smile
    d.ellipse(B(92.5, 116.5, 107.5, 127.5), fill="#1a0c04")
    d.arc(B(87.9, 108.8, 112.1, 133.0), start=42, end=138, fill="#1a0c04", width=int(2.2 * F))

    # Headphone band (top half-ellipse) with rounded ends
    d.arc(B(44, 66, 156, 144), start=180, end=360, fill="#1e1e30", width=int(9 * F))
    for x in (44 + 4.5, 156 - 4.5):
        d.ellipse(B(x - 4.5, 100.5, x + 4.5, 109.5), fill="#1e1e30")

    # Ear cups
    d.rounded_rectangle(B(29, 96, 52, 118), radius=7 * F, fill="#1e1e30")
    d.rounded_rectangle(B(33, 100, 48, 114), radius=4 * F, fill="#3a3a5c")
    d.rounded_rectangle(B(148, 96, 171, 118), radius=7 * F, fill="#1e1e30")
    d.rounded_rectangle(B(152, 100, 167, 114), radius=4 * F, fill="#3a3a5c")

    # Pink ring
    d.ellipse(B(5, 5, 195, 195), outline="#ff6eb4", width=int(2.8 * F))

    return img


def main() -> None:
    art = render()
    base = art.resize((256, 256), Image.LANCZOS)

    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base.save(ROOT / "assets" / "icon.ico", sizes=ico_sizes)
    base.save(ROOT / "src" / "overlay" / "static" / "icon.ico", sizes=ico_sizes)
    art.resize((64, 64), Image.LANCZOS).save(ROOT / "src" / "overlay" / "static" / "shiba-icon.png")
    print("icons written")


if __name__ == "__main__":
    main()
