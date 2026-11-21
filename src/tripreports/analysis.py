"""Everything computed from the GPX track and the trip file: day stats, totals, summit times."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from . import gpxstats as gs
from .plots import AltDay, DayPoint, PeakMark
from .schema import Trip


@dataclass
class GroupView:
    """One GPX file of several: its track and what its map and profile show."""

    name: object                 # heading above its figures (LText or None)
    track: gs.Track
    day_start_idx: list[int]     # indices into the group's own track
    rest_spans: list[tuple[dt.datetime, dt.datetime]]
    peaks: list[PeakMark]        # summits reached within the group
    distance_m: float            # calibrated like the day rows, so headlines match the tables
    ascent_m: float
    n_days: int


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
    groups: list[GroupView] = field(default_factory=list)
    expedition: list[AltDay] = field(default_factory=list)   # base camp stay, when base_camp is set


def analyse(trip: Trip, trip_dir: Path) -> Analysis:
    files = trip.gpx_files()
    track = gs.load_gpx([trip_dir / f.file for f in files], trip.timezone)
    parts = [gs.load_gpx(trip_dir / f.file, trip.timezone) for f in files] if len(files) > 1 else []
    shift = dt.timedelta(hours=trip.day_cutoff_hour)
    spans = [((p.t[0] - shift).date(), (p.t[-1] - shift).date()) for p in parts]
    # files that get their own map and profile (the others only count in the tables)
    plotted = [(f, p, span) for f, p, span in zip(files if parts else [], parts, spans, strict=True) if f.figures]
    tz = ZoneInfo(trip.timezone)
    warnings: list[str] = []

    dates = sorted({d.date for d in trip.days}) or [
        trip.start_date + dt.timedelta(days=i) for i in range((trip.end_date - trip.start_date).days + 1)
    ]

    def in_span(date: dt.date) -> bool:
        return any(a <= date <= b for a, b in spans)

    days, starts = [], []
    for date in dates:
        ds = gs.day_stats(track, date, trip.day_cutoff_hour)
        if ds is None:
            # with several files, days outside them (travel, rest in base camp) have no track; with a
            # base camp, neither has a day that starts and ends in the same camp (a rest day)
            if (not parts or in_span(date)) and not resting(trip, date):
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

    groups = []
    for f, sub, (first, last) in plotted:
        g_days = [d for d in days if first <= d.date <= last]
        g_starts = [int(np.flatnonzero(sub.t == d.start)[0]) for d in g_days]
        g_peaks = [m for m in marks if m.time is not None and sub.t[0] <= m.time <= sub.t[-1]]
        groups.append(GroupView(
            name=f.name, track=sub, day_start_idx=g_starts, rest_spans=gs.rests(sub), peaks=g_peaks,
            distance_m=float(sum(d.distance_m for d in g_days)),
            ascent_m=float(sum(d.ascent_m for d in g_days)),
            n_days=(last - first).days + 1))

    return Analysis(
        track=track,
        days=days,
        day_start_idx=starts,
        totals=totals,
        rest_spans=gs.rests(track),
        peaks=marks,
        warnings=warnings,
        factors=factors,
        groups=groups,
        expedition=expedition_days(trip, days),
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


def night_at(trip: Trip, date: dt.date) -> float | None:
    """Altitude of the night after ``date``: its accommodation entry, else base camp during the stay.
    None when the trip has no base camp or the date is outside the stay."""
    bc = trip.base_camp
    if bc is None or not bc.arrival <= date < bc.departure:
        return None
    slept = {a.date: a.altitude_m for a in trip.accommodation if a.altitude_m is not None}
    return slept.get(date, bc.altitude_m)


def resting(trip: Trip, date: dt.date) -> bool:
    """A day that starts and ends in the same camp of a base camp stay (needs no track)."""
    before, after = night_at(trip, date - dt.timedelta(days=1)), night_at(trip, date)
    return before is not None and before == after


def expedition_days(trip: Trip, days: list[gs.DayStats]) -> list[AltDay]:
    """Every day from arrival at base camp to departure: where it started and ended (the nights before
    and after it), its lowest and highest point, and where the night after it was spent.

    A night with an accommodation entry is at that altitude, every other night at base camp. A day
    with a track takes its lowest and highest point from it; a day without one (rest, a day in a high
    camp) spans the nights before and after it, and ``high_point_m`` of its diary entry. The range
    always includes both nights, so a camp never sits outside its day's bar.
    """
    bc = trip.base_camp
    if bc is None:
        return []
    slept = {a.date: a.altitude_m for a in trip.accommodation if a.altitude_m is not None}
    tracked = {d.date: d for d in days}
    high_points = {d.date: d.high_point_m for d in trip.days if d.high_point_m is not None}
    out: list[AltDay] = []
    before = bc.altitude_m
    date = bc.arrival
    while date <= bc.departure:
        night = None if date == bc.departure else slept.get(date, bc.altitude_m)
        ends = [before] + ([night] if night is not None else [])
        lo, hi = min(ends), max(ends)
        if date in tracked:
            lo, hi = min(lo, tracked[date].min_alt_m), max(hi, tracked[date].max_alt_m)
        if date in high_points:
            hi = max(hi, high_points[date])
        out.append(AltDay(date, before, night if night is not None else bc.altitude_m, lo, hi, night))
        before = night if night is not None else before
        date += dt.timedelta(days=1)
    return out
