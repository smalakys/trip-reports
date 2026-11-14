"""Everything computed from the GPX track and the trip file: day stats, totals, summit times."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from . import gpxstats as gs
from .plots import PeakMark
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

    return Analysis(
        track=track,
        days=days,
        day_start_idx=starts,
        totals=gs.total_stats(track, days),
        rest_spans=gs.rests(track),
        peaks=marks,
        warnings=warnings,
    )
