"""GPX loading and the statistics derived from it (distance, ascent, rests, summit times)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import gpxpy
import numpy as np
from scipy.signal import medfilt

EARTH_R = 6_371_000.0
REST_MIN_HOURS = 2.5      # a stop at least this long counts as a rest (night, long bivouac)
REST_SPEED = 0.12         # m/s; below this a segment counts as "not moving"
ASCENT_THRESHOLD_M = 3.0  # hysteresis for gain/loss, ignores GPS altitude noise


@dataclass
class Track:
    t: np.ndarray        # local-time datetimes (object array)
    lat: np.ndarray
    lon: np.ndarray
    ele_raw: np.ndarray
    ele: np.ndarray      # smoothed
    dist: np.ndarray     # cumulative horizontal distance, m (jitter-suppressed)
    tz: ZoneInfo

    def __len__(self) -> int:
        return len(self.t)


@dataclass
class DayStats:
    date: dt.date
    duration: dt.timedelta
    distance_m: float
    ascent_m: float
    descent_m: float
    min_alt_m: float
    max_alt_m: float
    start: dt.datetime
    end: dt.datetime
    end_alt_m: float  # altitude where the day's recording ends (the night's sleeping altitude)


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = p2 - p1, np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def load_gpx(path: str | Path | list[str | Path], tz_name: str) -> Track:
    """Load one GPX file, or several as one track in time order."""
    tz = ZoneInfo(tz_name)
    paths = path if isinstance(path, list) else [path]
    pts = []
    for one in paths:
        with open(one, encoding="utf-8") as fh:
            gpx = gpxpy.parse(fh)
        pts += [p for trk in gpx.tracks for seg in trk.segments for p in seg.points
                if p.time is not None and p.elevation is not None]
    if len(pts) < 2:
        raise ValueError(f"{', '.join(map(str, paths))}: need a track with timestamps and elevation")
    pts.sort(key=lambda p: p.time)
    t = np.array([p.time.astimezone(tz) for p in pts], dtype=object)
    lat = np.array([p.latitude for p in pts])
    lon = np.array([p.longitude for p in pts])
    ele_raw = np.array([p.elevation for p in pts], dtype=float)
    ele = medfilt(ele_raw, kernel_size=5)
    ele[:2], ele[-2:] = ele_raw[:2], ele_raw[-2:]
    step = haversine(lat[:-1], lon[:-1], lat[1:], lon[1:])
    dt_s = np.array([(b - a).total_seconds() for a, b in zip(t[:-1], t[1:], strict=True)])
    speed = step / np.maximum(dt_s, 1.0)
    step = np.where(speed < REST_SPEED, 0.0, step)  # suppress GPS jitter while standing still
    dist = np.concatenate([[0.0], np.cumsum(step)])
    return Track(t, lat, lon, ele_raw, ele, dist, tz)


def gain_loss(ele: np.ndarray, threshold: float = ASCENT_THRESHOLD_M) -> tuple[float, float]:
    """Ascent and descent with a hysteresis threshold so altitude noise does not accumulate."""
    if len(ele) < 2:
        return 0.0, 0.0
    up = down = 0.0
    ref = ele[0]
    for e in ele[1:]:
        if e - ref >= threshold:
            up += e - ref
            ref = e
        elif ref - e >= threshold:
            down += ref - e
            ref = e
    return float(up), float(down)


def rests(track: Track, min_hours: float = REST_MIN_HOURS) -> list[tuple[dt.datetime, dt.datetime]]:
    """Intervals where the track barely moves for at least ``min_hours`` (nights, long stops)."""
    t = track.t
    step = np.diff(track.dist)
    dt_s = np.array([(b - a).total_seconds() for a, b in zip(t[:-1], t[1:], strict=True)])
    still = step / np.maximum(dt_s, 1.0) < REST_SPEED
    out: list[tuple[dt.datetime, dt.datetime]] = []
    i = 0
    n = len(still)
    while i < n:
        if not still[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and still[j + 1]:
            j += 1
        start, end = t[i], t[j + 1]
        if (end - start).total_seconds() >= min_hours * 3600:
            out.append((start, end))
        i = j + 1
    return out


def _overlap(a0, a1, b0, b1) -> dt.timedelta:
    lo, hi = max(a0, b0), min(a1, b1)
    return max(hi - lo, dt.timedelta(0))


def day_stats(track: Track, date: dt.date, cutoff_hour: int = 0) -> DayStats | None:
    shifted = np.array([(x - dt.timedelta(hours=cutoff_hour)).date() for x in track.t])
    idx = np.flatnonzero(shifted == date)
    if len(idx) < 2:
        return None
    sl = slice(idx[0], idx[-1] + 1)
    start, end = track.t[idx[0]], track.t[idx[-1]]
    resting = sum((_overlap(start, end, a, b) for a, b in rests(track)), dt.timedelta(0))
    up, down = gain_loss(track.ele[sl])
    return DayStats(
        date=date,
        duration=(end - start) - resting,
        distance_m=float(track.dist[idx[-1]] - track.dist[idx[0]]),
        ascent_m=up,
        descent_m=down,
        min_alt_m=float(track.ele[sl].min()),
        max_alt_m=float(track.ele[sl].max()),
        start=start,
        end=end,
        end_alt_m=float(track.ele[idx[-1]]),
    )


def find_summit(track: Track, lat: float, lon: float, radius_m: float = 120.0) -> dt.datetime | None:
    """Arrival time at a summit: the first track point near it that is also close to its top.

    Looks at points within ``radius_m`` horizontally and picks the first one within a few metres
    of the highest altitude reached there; None if the track never comes near.
    """
    d = haversine(track.lat, track.lon, lat, lon)
    near = np.flatnonzero(d <= radius_m)
    if len(near) == 0:
        return None
    top = track.ele[near].max()
    first = near[track.ele[near] >= top - 8.0][0]
    return track.t[first]


def total_stats(track: Track, days: list[DayStats]) -> dict:
    up, down = gain_loss(track.ele)
    return {
        "distance_m": float(track.dist[-1]),
        "ascent_m": float(sum(d.ascent_m for d in days)) if days else up,
        "descent_m": float(sum(d.descent_m for d in days)) if days else down,
        "min_alt_m": float(track.ele.min()),
        "max_alt_m": float(track.ele.max()),
        "net_time": sum((d.duration for d in days), dt.timedelta(0)),
    }
