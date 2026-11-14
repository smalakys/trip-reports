"""Map tiles for the route map: fetched once, then cached in the trip folder.

The first build with ``map.basemap: tiles`` downloads the tiles that cover the route
(OpenTopoMap by default) and stores the stitched image as ``basemap.jpg`` plus ``basemap.json``
(its extent and attribution) next to ``trip.yaml``. Later builds use that cache, so they work
offline and do not hit the tile server again. Delete the two files to fetch afresh.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

R_MERC = 6_378_137.0

SOURCES = {
    "topo": ("OpenTopoMap", "© OpenStreetMap contributors, SRTM | map style © OpenTopoMap (CC-BY-SA)"),
    "light": ("CartoDB.PositronNoLabels", "© OpenStreetMap contributors, © CARTO"),
}


@dataclass
class Basemap:
    image: Image.Image
    extent: tuple[float, float, float, float]   # xmin, xmax, ymin, ymax in web mercator metres
    attribution: str


def merc_to_lonlat(x: float, y: float) -> tuple[float, float]:
    lon = math.degrees(x / R_MERC)
    lat = math.degrees(2 * math.atan(math.exp(y / R_MERC)) - math.pi / 2)
    return lon, lat


def _fetch(extent, source: str, zoom: int | None) -> Basemap:
    import contextily as cx

    name, attribution = SOURCES[source]
    provider = cx.providers
    for part in name.split("."):
        provider = provider[part]
    xmin, xmax, ymin, ymax = extent
    west, south = merc_to_lonlat(xmin, ymin)
    east, north = merc_to_lonlat(xmax, ymax)
    if zoom is None:   # about 3000 px across the view: 256 px tiles, 2**zoom tiles around 40 075 017 m
        zoom = max(1, min(16, round(math.log2(3000 * 40_075_016.7 / (256 * (xmax - xmin))))))
    img, ext = cx.bounds2img(west, south, east, north, zoom=zoom, source=provider, ll=True)
    return Basemap(Image.fromarray(img[..., :3]), (ext[0], ext[1], ext[2], ext[3]), attribution)


def _trim(bm: Basemap, extent: tuple[float, float, float, float], max_px: int) -> Basemap:
    """Cut the stitched tiles down to the wanted extent and cap their size (keeps the cache small)."""
    xmin, xmax, ymin, ymax = bm.extent
    w, h = bm.image.size
    ex0, ex1, ey0, ey1 = extent
    box = (max(0, math.floor((ex0 - xmin) / (xmax - xmin) * w)), max(0, math.floor((ymax - ey1) / (ymax - ymin) * h)),
           min(w, math.ceil((ex1 - xmin) / (xmax - xmin) * w)), min(h, math.ceil((ymax - ey0) / (ymax - ymin) * h)))
    im = bm.image.crop(box)
    new_extent = (xmin + box[0] / w * (xmax - xmin), xmin + box[2] / w * (xmax - xmin),
                  ymax - box[3] / h * (ymax - ymin), ymax - box[1] / h * (ymax - ymin))
    if im.size[0] > max_px:
        im = im.resize((max_px, round(im.size[1] * max_px / im.size[0])), Image.LANCZOS)
    return Basemap(im, new_extent, bm.attribution)


def load_basemap(trip_dir: Path, extent: tuple[float, float, float, float], source: str = "topo",
                 zoom: int | None = None) -> Basemap:
    """Return the cached basemap for the trip, fetching and caching it on first use."""
    if source not in SOURCES:
        raise ValueError(f"unknown tile source {source!r}; choose from {sorted(SOURCES)}")
    jpg, meta = trip_dir / "basemap.jpg", trip_dir / "basemap.json"
    if jpg.exists() and meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        xmin, xmax, ymin, ymax = m["extent"]
        need = extent
        if xmin <= need[0] and need[1] <= xmax and ymin <= need[2] and need[3] <= ymax and m["source"] == source:
            return Basemap(Image.open(jpg).convert("RGB"), tuple(m["extent"]), m["attribution"])
    bm = _fetch(extent, source, zoom)
    bm = _trim(bm, extent, max_px=2600)
    bm.image.save(jpg, quality=82, optimize=True)
    meta.write_text(json.dumps({"source": source, "extent": list(bm.extent), "attribution": bm.attribution},
                               indent=1), encoding="utf-8")
    return bm


def crop_and_tone(bm: Basemap, view: tuple[float, float, float, float], desaturate: float = 0.7,
                  lighten: float = 0.12) -> Image.Image:
    """Crop the basemap to the view extent; mute its colours so the route reads first."""
    xmin, xmax, ymin, ymax = bm.extent
    w, h = bm.image.size
    vx0, vx1, vy0, vy1 = view
    box = (round((vx0 - xmin) / (xmax - xmin) * w), round((ymax - vy1) / (ymax - ymin) * h),
           round((vx1 - xmin) / (xmax - xmin) * w), round((ymax - vy0) / (ymax - ymin) * h))
    im = bm.image.crop(box)
    im = ImageEnhance.Color(im).enhance(1 - desaturate)
    arr = np.asarray(im, dtype=float)
    arr = arr + (255 - arr) * lighten
    return Image.fromarray(arr.clip(0, 255).astype("uint8"))
