"""Everything computed from the GPX track and the trip file: day stats, totals, summit times."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from . import gpxstats as gs
from .plots import DayPoint, PeakMark
from .schema import Trip


@dataclass
class Analysis:
    track: gs.Track
    days: list[gs.DayStats]
    day_start_idx: list[int]
    totals: dict
    rest_spans: list[tuple[dt.datetime, dt.datetime]]
    peaks: list[PeakMark]
    warnings: list[str]
    factors: dict | None = None    # distance / ascent / descent scale factors when calibrated


def analyse(trip: Trip, trip_dir: Path) -> Analysis:
    track = gs.load_gpx(trip_dir / trip.gpx, trip.timezone)
    tz = ZoneInfo(trip.timezone)
    warnings: list[str] = []

    dates = sorted({d.date for d in trip.days}) or [
        trip.start_date + dt.timedelta(days=i) for i in range((trip.end_date - trip.start_date).days + 1)
    ]
    days, starts = [], []
    for date in dates:
        ds = gs.day_stats(track, date, trip.day_cutoff_hour)
        if ds is None:
            warnings.append(f"no GPX points on {date}")
            continue
        days.append(ds)
        starts.append(int(np.flatnonzero(track.t == ds.start)[0]))

    marks: list[PeakMark] = []
    for p in trip.peaks:
        when: dt.datetime | None = None
        if p.time is not None:
            date = p.date
            if date is None and p.lat is not None and p.lon is not None:
                found = gs.find_summit(track, p.lat, p.lon)
                date = found.date() if found else None
            if date is not None:
                hh, mm = map(int, p.time.split(":"))
                when = dt.datetime.combine(date, dt.time(hh, mm), tzinfo=tz)
        elif p.lat is not None and p.lon is not None:
            when = gs.find_summit(track, p.lat, p.lon)
            if when is None:
                warnings.append(f"track never comes near {p.name} (lat/lon may be wrong)")
        marks.append(PeakMark(p.name, p.elevation_m, when, p.lat, p.lon))

    totals = gs.total_stats(track, days)
    factors = None
    cal = trip.calibration
    if cal is not None:
        f_dist = cal.distance_km * 1000 / totals["distance_m"] if cal.distance_km else 1.0
        f_up = cal.ascent_m / totals["ascent_m"] if cal.ascent_m else 1.0
        f_down = cal.descent_m / totals["descent_m"] if cal.descent_m else f_up
        for d in days:
            d.distance_m *= f_dist
            d.ascent_m *= f_up
            d.descent_m *= f_down
        totals["distance_m"] *= f_dist
        totals["ascent_m"] *= f_up
        totals["descent_m"] *= f_down
        factors = {"distance": f_dist, "ascent": f_up, "descent": f_down}

    return Analysis(
        track=track,
        days=days,
        day_start_idx=starts,
        totals=totals,
        rest_spans=gs.rests(track),
        peaks=marks,
        warnings=warnings,
        factors=factors,
    )


def acclimatisation_points(an: Analysis, day_label) -> tuple[list[DayPoint], tuple[str, float, int] | None]:
    """Per-day high point and sleeping altitude, plus the highest summit as (name, altitude, day).

    ``day_label(n)`` makes the axis label for day ``n`` (1-based). The last day has no sleeping
    altitude: the trip ends when it does.
    """
    points = []
    for i, d in enumerate(an.days):
        last = i == len(an.days) - 1
        points.append(DayPoint(day_label(i + 1), d.max_alt_m, None if last else d.end_alt_m))
    summit = None
    timed = [p for p in an.peaks if p.time is not None]
    if timed:
        top = max(timed, key=lambda p: p.elevation_m)
        for i, d in enumerate(an.days):
            if d.start <= top.time <= d.end:
                # plot the day's high point (GPS) at the day, label with the official height
                summit = (top.name, top.elevation_m, i)
                break
    return points, summit
