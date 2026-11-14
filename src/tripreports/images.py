"""Image preparation: orientation, downscaling for print, JPEG re-encoding."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


def prepare_image(src: Path, dst: Path, long_edge_px: int, quality: int) -> tuple[int, int]:
    """Write a downscaled, orientation-corrected JPEG; returns its (width, height) in pixels."""
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        w, h = im.size
        scale = min(1.0, long_edge_px / max(w, h))
        if scale < 1.0:
            im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        im.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
        return im.size
