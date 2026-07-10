#!/usr/bin/env python3
"""Generate multi-resolution favicon assets from the QM symbol master PNG."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

INSTALLER_DIR = Path(__file__).resolve().parent
ASSETS_DIR = INSTALLER_DIR / "assets"
MASTER = ASSETS_DIR / "qm_symbol_black_512.png"
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _qm_mark_source() -> Image.Image:
    if not MASTER.is_file():
        raise FileNotFoundError(f"Missing icon master: {MASTER}")
    return Image.open(MASTER).convert("RGBA")


def render_icon(mark: Image.Image, size: int) -> Image.Image:
    mark = mark.copy()
    bbox = mark.getbbox()
    if bbox:
        mark = mark.crop(bbox)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pad = max(1, size // 10)
    max_w = size - 2 * pad
    max_h = size - 2 * pad
    scale = min(max_w / mark.width, max_h / mark.height)
    width = max(1, int(mark.width * scale))
    height = max(1, int(mark.height * scale))
    resized = mark.resize((width, height), Image.Resampling.LANCZOS)
    canvas.paste(resized, ((size - width) // 2, (size - height) // 2), resized)
    return canvas


def generate_icons() -> None:
    mark = _qm_mark_source()
    icons = [render_icon(mark, size) for size in ICO_SIZES]

    icons[-1].save(
        ASSETS_DIR / "qm_favicon.ico",
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=icons[:-1],
    )
    icons[ICO_SIZES.index(32)].save(ASSETS_DIR / "qm_favicon_32.png")
    icons[-1].save(ASSETS_DIR / "qm_favicon_256.png")


if __name__ == "__main__":
    generate_icons()
    print(f"Wrote {ASSETS_DIR / 'qm_favicon.ico'} with sizes: {', '.join(str(s) for s in ICO_SIZES)}")
