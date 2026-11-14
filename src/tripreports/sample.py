"""A small fictional sample trip, generated on demand: GPS track, placeholder pictures, trip file.

``tripreport sample DEST`` writes a complete trip folder you can build to try the tool, and the
test suite builds the same trip. Nothing here is real data: the people, peaks, huts and track are
invented, and the pictures are drawn, not photographed.
"""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import gpxpy.gpx
import numpy as np
from PIL import Image, ImageFilter

LAT0, LON0 = 46.5000, 8.0000
TZ = ZoneInfo("Europe/Zurich")
SCALE = 3.0  # stretch the local frame so walking speeds look realistic

# (kind, "MM-DD HH:MM", east_m, north_m, elevation_m)
#   move: travel in a straight-ish line, arriving at the given time
#   stay: remain at the current place until the given time (position args ignored)
LEGS: list[tuple] = [
    ("start", "08-10 09:00", 0, 0, 1300),
    ("move", "08-10 12:15", 800, 400, 2000),
    ("move", "08-10 16:30", 1500, 1000, 2850),   # Hut Alpha
    ("stay", "08-11 03:30"),
    ("move", "08-11 08:10", 1870, 1300, 3987),   # Ledo smailė
    ("stay", "08-11 08:25"),
    ("move", "08-11 11:30", 2230, 1370, 4105),   # Žaibo kupolas
    ("stay", "08-11 11:45"),
    ("move", "08-11 13:45", 2530, 1600, 4168),   # Audros ragas
    ("stay", "08-11 14:00"),
    ("move", "08-11 18:00", 2000, 1870, 3350),   # Hut Beta
    ("stay", "08-12 04:00"),
    ("move", "08-12 07:30", 1730, 2200, 4010),   # Sidabro kalnas
    ("stay", "08-12 10:45"),   # a long stop at the summit shelter
    ("move", "08-12 11:20", 2030, 2500, 4231),   # Aušros viršūnė
    ("stay", "08-12 11:40"),
    ("move", "08-12 15:00", 2330, 2600, 3900),   # col bivouac
    ("stay", "08-13 05:00"),
    ("move", "08-13 09:00", 2730, 2870, 4087),   # Vėjo dantis
    ("stay", "08-13 09:15"),
    ("move", "08-13 14:30", 3130, 2070, 3100),   # Hut Gamma
    ("stay", "08-14 06:00"),
    ("move", "08-14 09:30", 2670, 1170, 2200),
    ("move", "08-14 12:30", 100, 30, 1300),      # back in the village
]



def to_latlon(east: float, north: float) -> tuple[float, float]:
    lat = LAT0 + north * SCALE / 111_320.0
    lon = LON0 + east * SCALE / (111_320.0 * math.cos(math.radians(LAT0)))
    return lat, lon


def _t(stamp: str) -> dt.datetime:
    return dt.datetime.strptime(f"2025-{stamp}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


def make_track(seed: int = 7):
    rng = np.random.default_rng(seed)
    pts: list[tuple[dt.datetime, float, float, float]] = []
    cur = None  # (time, east, north, ele)
    for leg in LEGS:
        kind, stamp = leg[0], leg[1]
        t1 = _t(stamp)
        if kind == "start":
            cur = (t1, *leg[2:])
            pts.append(cur)
            continue
        t0, x0, y0, z0 = cur
        if kind == "stay":
            step = dt.timedelta(minutes=5 if (t1 - t0) > dt.timedelta(hours=1) else 1)
            t = t0 + step
            while t < t1:
                pts.append((t, x0, y0, z0))
                t += step
            pts.append((t1, x0, y0, z0))
            cur = (t1, x0, y0, z0)
            continue
        x1, y1, z1 = leg[2:]
        n = int((t1 - t0).total_seconds() // 15)
        s = np.linspace(0, 1, n + 1)[1:]
        # uneven pace: smooth random time warp
        warp = np.cumsum(1 + 0.35 * np.convolve(rng.standard_normal(n), np.ones(40) / 40, "same"))
        s = np.clip(warp / warp[-1], 0, 1)
        length = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / max(length, 1), (x1 - x0) / max(length, 1)
        wiggle = 0.04 * length * np.sin(2 * math.pi * 3 * s) * np.sin(math.pi * s)
        for i, si in enumerate(s):
            t = t0 + dt.timedelta(seconds=15 * (i + 1))
            pts.append((t, x0 + (x1 - x0) * si + nx * wiggle[i],
                        y0 + (y1 - y0) * si + ny * wiggle[i], z0 + (z1 - z0) * si))
        cur = (t1, x1, y1, z1)
    out = []
    for t, x, y, z in pts:
        lat, lon = to_latlon(x, y)
        lat += rng.normal(0, 2.5) / 111_320.0
        lon += rng.normal(0, 2.5) / (111_320.0 * math.cos(math.radians(LAT0)))
        out.append((t, lat, lon, z + rng.normal(0, 1.8)))
    return out


def write_gpx(path: Path) -> None:
    gpx = gpxpy.gpx.GPX()
    gpx.creator = "tripreports sample"
    trk = gpxpy.gpx.GPXTrack(name="Sample traverse")
    seg = gpxpy.gpx.GPXTrackSegment()
    for t, lat, lon, ele in make_track():
        seg.points.append(gpxpy.gpx.GPXTrackPoint(
            round(lat, 6), round(lon, 6), elevation=round(ele, 1), time=t.astimezone(dt.UTC)))
    trk.segments.append(seg)
    gpx.tracks.append(trk)
    path.write_text(gpx.to_xml(), encoding="utf-8")


PALETTES = {
    "dawn":   dict(top=(46, 62, 112), hor=(255, 168, 110), sun=(255, 214, 160), haze=(236, 168, 150)),
    "day":    dict(top=(58, 120, 196), hor=(190, 218, 240), sun=(255, 250, 235), haze=(190, 214, 238)),
    "dusk":   dict(top=(40, 44, 92), hor=(250, 120, 84), sun=(255, 190, 120), haze=(206, 130, 140)),
    "storm":  dict(top=(88, 96, 112), hor=(176, 184, 196), sun=(220, 224, 230), haze=(170, 178, 192)),
    "cold":   dict(top=(70, 110, 170), hor=(220, 232, 244), sun=(255, 255, 255), haze=(206, 222, 240)),
}


def _noise(rng, n, octaves=6, rough=0.55, ridged=True):
    x = np.linspace(0, 1, n)
    out = np.zeros(n)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        k = 2 ** (o + 1)
        v = np.interp(x, np.linspace(0, 1, k + 1), rng.random(k + 1))
        v = 1 - np.abs(2 * v - 1) if ridged else v
        out += amp * v
        tot += amp
        amp *= rough
    return out / tot


def landscape(w: int, h: int, palette: str, seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    p = {k: np.array(v, float) for k, v in PALETTES[palette].items()}
    yy, xx = np.mgrid[0:h, 0:w]
    horizon = 0.62 * h
    f = np.clip(yy / horizon, 0, 1)[..., None]
    img = p["top"] * (1 - f) + p["hor"] * f
    sx, sy = rng.uniform(0.25, 0.75) * w, rng.uniform(0.38, 0.52) * h
    glow = np.exp(-(((xx - sx) / (0.35 * w)) ** 2 + ((yy - sy) / (0.22 * h)) ** 2))[..., None]
    img = img * (1 - 0.6 * glow) + p["sun"] * 0.6 * glow
    rows = np.arange(h)[:, None]
    n_layers = 5
    for layer in range(n_layers):
        depth = layer / (n_layers - 1)                     # 0 = far, 1 = near
        base = h * (0.52 + 0.30 * depth)
        relief = h * (0.46 - 0.22 * depth)
        top = base - relief * _noise(rng, w, octaves=8, rough=0.62 - 0.1 * depth) ** 1.7
        slope = np.gradient(top) * (w / 700)
        col_shade = np.clip(1 + 0.8 * slope, 0.55, 1.3)
        below = rows - top[None, :]
        mask = (below >= 0).astype(float)
        # gullies fan out diagonally down the faces: shear the per-column lighting with depth
        shear = (xx + np.clip(below, 0, None) * (0.55 + 0.4 * rng.random())).astype(int) % w
        gully = 0.86 + 0.28 * _noise(rng, w, 6, 0.45, False)[shear]
        shade = col_shade[shear] * gully
        snowline = (h * (0.16 - 0.08 * depth)) * (0.4 + 1.2 * _noise(rng, w, 6, 0.6, False))[None, :]
        snow = np.clip((snowline - below) / np.maximum(snowline * 0.5, 1) + 0.25 * (shade - 1), 0, 1) * mask
        rock = (np.array([92, 86, 92]) * (1 - 0.3 * depth))[None, None, :]
        col = rock * shade[..., None]
        snow_col = np.array([244, 247, 252]) * np.clip(shade, 0.62, 1.08)[..., None]
        col = col * (1 - snow[..., None]) + snow_col * snow[..., None]
        haze = (1 - depth) ** 1.6 * 0.75
        col = col * (1 - haze) + p["haze"][None, None, :] * haze
        edge = np.clip(mask, 0, 1)
        img = img * (1 - edge[..., None]) + col * edge[..., None]
        if layer < n_layers - 2:
            img = np.asarray(Image.fromarray(img.clip(0, 255).astype("uint8")).filter(
                ImageFilter.GaussianBlur(1.2 - layer * 0.3)), float)
    # dark foreground rocks
    fg = h * (0.90 - 0.05 * _noise(rng, w, 8, 0.7))
    fgm = (rows >= fg[None, :])[..., None]
    img = np.where(fgm, np.array([38, 38, 44]) + rng.normal(0, 4, (h, w, 1)), img)
    vign = 1 - 0.28 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 2
    img = img * vign[..., None] + rng.normal(0, 1.6, (h, w, 1))
    return Image.fromarray(img.clip(0, 255).astype("uint8"))




TRIP_YAML = """\
# yaml-language-server: $schema=../../schema/trip.schema.json
# SAMPLE: fictional people, peaks, huts and track, generated by `tripreport sample`.
schema_version: 1
languages: [lt]

title: Aušros grandinė
subtitle: Ledo smailė – Aušros viršūnė – Vėjo dantis
cover:
  image: photos/cover.jpg
  kicker: Įkopimo ataskaita

start_date: 2025-08-10
end_date: 2025-08-14
timezone: Europe/Zurich
region: Aušros Alpės (išgalvotas rajonas)
country: Šveicarija
kind: Techninė klasė

participants:
  - name: Jonas Jonaitis
  - name: Rūta Rutaitė

peaks:
  - {name: Ledo smailė, elevation_m: 3987, lat: 46.53503, lon: 8.07321}
  - {name: Žaibo kupolas, elevation_m: 4105, lat: 46.53692, lon: 8.08731}
  - {name: Audros ragas, elevation_m: 4168, lat: 46.54312, lon: 8.09905}
  - {name: Sidabro kalnas, elevation_m: 4010, lat: 46.55929, lon: 8.06773}
  - {name: Aušros viršūnė, elevation_m: 4231, lat: 46.56737, lon: 8.07948}
  - {name: Vėjo dantis, elevation_m: 4087, lat: 46.57734, lon: 8.10688}

route_description: >-
  Penkių dienų žygis per šešias išgalvotas viršūnes, kiekviena aukštesnė nei 3980 m. Pradėta ir
  baigta slėnio kaimelyje, trys naktys praleistos trobelėse, viena – bivake ant perėjos.

routes:
  - name: Ledo grandinė
    grade: AD
    grade_system: Alpine
    note: III · 700 m
    sections:
      - {name: Ledo smailė, grade: PD, pitches: "1", leader: Jonas}
      - {name: Žaibo kupolas, grade: PD+, pitches: "2", leader: Pakaitomis}
      - {name: Audros ragas, grade: AD, pitches: "3", leader: Rūta, note: Trapūs akmenys viršutinėje dalyje}
  - name: Aušros keteros
    grade: D−
    grade_system: Alpine
    sections:
      - {name: Sidabro kalnas, grade: AD, pitches: "2", leader: Rūta}
      - {name: Aušros viršūnė, grade: D−, pitches: "4", leader: Pakaitomis}
      - {name: Vėjo dantis, grade: AD, pitches: "1", leader: Jonas}

tactics: Lipome susijungę virve su slenkančia sauga, techninėse vietose – su apatine sauga.
gear:
  - 1 × 60 m virvė
  - 6 × kamalotai
  - 4 × ledo sraigtai
conditions: Slėnyje dieną buvo apie 26 °C, 4000 m aukštyje – apie 0–5 °C.

accommodation:
  - {date: 2025-08-10, place: Alfos trobelė, kind: Trobelė, altitude_m: 2850}
  - {date: 2025-08-11, place: Beta trobelė, kind: Trobelė, altitude_m: 3350}
  - {date: 2025-08-12, place: Perėjos bivakas, kind: Bivakas, altitude_m: 3900}
  - {date: 2025-08-13, place: Gama trobelė, kind: Trobelė, altitude_m: 3100}
breaks:
  - {date: 2025-08-12, place: Sidabro prieglauda}

days:
  - date: 2025-08-10
    title: Slėnis – Alfos trobelė
    text: >-
      Išėjome 09:00 iš slėnio kaimelio. Dienos duomenys: {distance}, apie {ascent} pakilimo per {hours}
  - date: 2025-08-11
    title: Ledo grandinė
    text: >-
      Startavome 03:30. **Ledo smailė** pasiekta 08:10, **Žaibo kupolas** – 11:30, o Audros rage
      akmenys buvo trapūs.


      Dienos duomenys: {distance}, apie {ascent} pakilimo ir {descent} nusileidimo per {hours}
  - date: 2025-08-12
    title: Aušros viršūnė
    text: >-
      **Sidabro kalnas** – 07:30, **Aušros viršūnė** – 11:20. Naktį praleidome bivake ant perėjos.
  - date: 2025-08-13
    title: Vėjo dantis
    text: >-
      Ankstyvas startas ir ilga ketera iki **Vėjo danties** (9:00).
  - date: 2025-08-14
    title: Žemyn į slėnį
    text: >-
      Nusileidome į slėnį ir 12:30 buvome kaimelyje.

gpx: track.gpx
map:
  basemap: plain
  color_by: none

photos:
  - {file: photos/a.jpg, size: half, caption: "Iliustracija: takas slėnyje."}
  - {file: photos/b.jpg, size: half, caption: "Iliustracija: ketera ryte."}
  - {file: photos/c.jpg, size: full, caption: "Iliustracija: nusileidimas."}

references:
  - "Fictional Alpine Club (2024). A guide to the Dawn Alps."
"""

PICTURES = [  # name, size, palette, seed
    ("cover.jpg", (900, 1273), "dawn", 11),
    ("a.jpg", (900, 600), "day", 21),
    ("b.jpg", (900, 600), "dawn", 23),
    ("c.jpg", (900, 600), "cold", 24),
]


def create_sample(dest: str | Path) -> Path:
    """Write the sample trip folder (trip.yaml, track.gpx, photos/) and return its path."""
    dest = Path(dest)
    (dest / "photos").mkdir(parents=True, exist_ok=True)
    (dest / "trip.yaml").write_text(TRIP_YAML, encoding="utf-8")
    write_gpx(dest / "track.gpx")
    for name, (w, h), palette, seed in PICTURES:
        landscape(w, h, palette, seed).save(dest / "photos" / name, quality=82, optimize=True)
    return dest
