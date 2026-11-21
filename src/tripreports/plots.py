"""Figures in the LAA plot style: elevation profile, route map, climb-high-sleep-low chart.

Plain inputs in, an SVG file out. Every colour, font and size comes from the resolved theme
(design tokens), so light and dark builds differ only in the token values.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402

from .gpxstats import Track  # noqa: E402
from .i18n import Locale  # noqa: E402
from .theme import FONTS_DIR, text_width_mm  # noqa: E402

MM = 1 / 25.4
R_MERC = 6_378_137.0
PX = 0.75  # points per CSS px


@dataclass
class PeakMark:
    name: str
    elevation_m: float
    time: dt.datetime | None  # local time of the summit, if known
    lat: float | None = None
    lon: float | None = None


@dataclass
class AltDay:
    """One day of the expedition altitude chart."""

    date: dt.date
    open_m: float           # where the day started: the night before (base camp on arrival)
    close_m: float          # where it ended: the night after (base camp on departure)
    low_m: float
    high_m: float
    night_m: float | None   # altitude slept at after this day; None on the day the stay ends


@dataclass
class DayPoint:
    """One day of the climb-high-sleep-low chart."""

    label: str
    high_m: float
    sleep_m: float | None  # None on the last day (no night after it)


class Fonts:
    """Font properties for the three token families."""

    def __init__(self, theme: dict):
        t = theme["type"]
        self.sans = FontProperties(family=theme["fonts"]["sans"], weight=400, size=t["body-sm"]["size"])
        self.sans_semibold = FontProperties(family=theme["fonts"]["sans"], weight=600,
                                            size=t["body-sm"]["size"])
        self.tick = FontProperties(family=theme["fonts"]["numeric"], weight=500, size=t["tick"]["size"])
        self.peak = FontProperties(family=theme["fonts"]["numeric"], weight=600,
                                   size=15 * PX)  # the design system's `peak` annotation
        self.muted = FontProperties(family=theme["fonts"]["sans"], weight=400, size=t["tick"]["size"])


def setup_style(theme: dict) -> Fonts:
    for ttf in FONTS_DIR.glob("*.ttf"):
        font_manager.fontManager.addfont(str(ttf))
    c = theme["colors"]
    plt.rcParams.update({
        "svg.fonttype": "path",
        "font.family": theme["fonts"]["sans"],
        "text.color": c["ink"],
        "axes.edgecolor": c["line-strong"],
        "axes.linewidth": 0.75,
        "axes.labelcolor": c["ink-muted"],
        "axes.facecolor": c["surface-000"],
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "xtick.color": c["ink-muted"],
        "ytick.color": c["ink-muted"],
        "figure.facecolor": c["surface-000"],
        "savefig.facecolor": c["surface-000"],
        "lines.solid_capstyle": "round",
    })
    return Fonts(theme)


def _halo(color: str, w: float = 2.5):
    return [pe.withStroke(linewidth=w, foreground=color)]


def _style_cartesian(ax, theme: dict, fonts: Fonts) -> None:
    """Horizontal gridlines only, a line-strong baseline, tick labels in the numeric face."""
    c = theme["colors"]
    ax.yaxis.grid(True, color=c["chart-grid"], lw=0.75)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)
    ax.tick_params(axis="x", pad=6)
    ax.tick_params(axis="y", pad=4)
    for lab in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
        lab.set_fontproperties(fonts.tick)
        lab.set_color(c["ink-muted"])


def _round_floor(v: float, step: float) -> float:
    return math.floor(v / step) * step


def _alt_ticks(lo: float, hi: float, step: float = 500.0) -> list[float]:
    return [float(v) for v in np.arange(lo, hi + 0.001, step)]


# --------------------------------------------------------------------------------------------
# Label placement for the profile: flags beside vertical leaders
# --------------------------------------------------------------------------------------------

def _flag_layout(labels: list[tuple[float, float]], left_limit: float) -> list[tuple[int, str]]:
    """Choose a row and side for each label hanging beside a vertical leader.

    ``labels`` holds (leader x, label width) in pixels, in drawing order. Labels in one row must
    not overlap and leaders must not cross labels. Earlier labels are moved to other rows or
    sides when that is what lets a later one be placed cleanly; if no clean layout exists, only
    overlaps within a row are avoided. Returns (row, side) per label, side "right" (label left
    of its leader) or "left".
    """

    def box(xc: float, w: float, side: str) -> tuple[float, float]:
        return (xc - w - 3, xc + 3) if side == "right" else (xc - 3, xc + w + 3)

    def clashes(items: list, xc: float, w: float, row: int, side: str, strict: bool) -> bool:
        x0, x1 = box(xc, w, side)
        for ox0, ox1, oxc, orow in items:
            if orow == row and not (x1 < ox0 or x0 > ox1):
                return True
            if strict and orow < row and ox0 <= xc <= ox1:   # our leader crosses that label
                return True
            if strict and orow > row and x0 <= oxc <= x1:    # their leader crosses our label
                return True
        return False

    def options(xc: float, w: float) -> list[tuple[int, str]]:
        sides = ["right", "left"] if xc - w - 3 > left_limit else ["left", "right"]
        return [(row, side) for row in range(6) for side in sides]

    budget = [5000]   # search steps; a handful of summits never comes close

    def search(i: int, items: list) -> list[tuple[int, str]] | None:
        if i == len(labels):
            return []
        xc, w = labels[i]
        for row, side in options(xc, w):
            budget[0] -= 1
            if budget[0] < 0:
                return None
            if clashes(items, xc, w, row, side, True):
                continue
            rest = search(i + 1, [*items, (*box(xc, w, side), xc, row)])
            if rest is not None:
                return [(row, side), *rest]
        return None

    clean = search(0, [])
    if clean is not None:
        return clean
    out, items = [], []
    for xc, w in labels:   # no clean layout: greedy, rows only kept apart
        sides = options(xc, w)[:2]
        choice = next(((r, s) for r, s in sides if not clashes(items, xc, w, r, s, True)), None)
        if choice is None:
            side = sides[0][1]
            choice = (next(r for r in range(64) if not clashes(items, xc, w, r, side, False)), side)
        out.append(choice)
        items.append((*box(xc, w, choice[1]), xc, choice[0]))
    return out


# --------------------------------------------------------------------------------------------
# Elevation profile
# --------------------------------------------------------------------------------------------

def _strip_rows(extents: list[tuple[float, float]], pad: float = 6.0) -> list[int]:
    """Row for each label in a strip, given its (x0, x1) in pixels: the lowest row where it does not
    overlap a label already placed (``pad`` pixels apart)."""
    rows: list[int] = []
    placed: list[tuple[float, float, int]] = []
    for x0, x1 in extents:
        row = 0
        while any(r == row and not (x1 + pad < o0 or x0 > o1 + pad) for o0, o1, r in placed):
            row += 1
        rows.append(row)
        placed.append((x0, x1, row))
    return rows


def _day_axis(t0: dt.datetime, t1: dt.datetime, min_hours: float = 4.0
              ) -> tuple[list[tuple[dt.date, dt.datetime]], list[dt.datetime]]:
    """Day labels and midnight lines for a profile running from ``t0`` to ``t1`` (naive local times).

    Every calendar day in the span is labelled at the middle of its visible part, including days
    without track points (a rest day in a tent); only a sliver of a day at either end, shorter
    than ``min_hours``, goes unlabelled. Returns ([(date, label position)], [midnights inside]).
    """
    labelled, midnights = [], []
    d = t0.date()
    while d <= t1.date():
        start = dt.datetime.combine(d, dt.time(0))
        lo, hi = max(start, t0), min(start + dt.timedelta(days=1), t1)
        if hi - lo >= dt.timedelta(hours=min_hours):
            labelled.append((d, lo + (hi - lo) / 2))
        if t0 < start < t1:
            midnights.append(start)
        d += dt.timedelta(days=1)
    return labelled, midnights


def elevation_profile(
    track: Track,
    rest_spans: list[tuple[dt.datetime, dt.datetime]],
    peaks: list[PeakMark],
    theme: dict,
    loc: Locale,
    out: Path,
    rest_labels: list[str | None] | None = None,
    height_ratio: float = 0.44,
) -> float:
    """Altitude against time, filled to the baseline, summits called out. Returns height/width.

    ``rest_labels`` names each rest span (for example the hut slept at); a span without a name
    is labelled with the generic word for night.
    """
    fonts = setup_style(theme)
    c = theme["colors"]
    width_in = text_width_mm(theme) * MM
    height_in = width_in * height_ratio
    fig, ax = plt.subplots(figsize=(width_in, height_in))

    naive = [x.replace(tzinfo=None) for x in track.t]
    t = mdates.date2num(naive)
    ele = track.ele
    lo = _round_floor(ele.min() - 100, 500)
    hi_data = float(ele.max())

    for a, b in rest_spans:
        ax.axvspan(mdates.date2num(a.replace(tzinfo=None)), mdates.date2num(b.replace(tzinfo=None)),
                   color=c["surface-200"], lw=0, zorder=0)
    ax.fill_between(t, ele, lo, color=c["chart-area"], lw=0, zorder=2)
    ax.plot(t, ele, color=c["series-1"], lw=2 * PX, zorder=3)
    ax.set_xlim(t[0], t[-1])

    # Summit labels: elevation in the `peak` weight over the name, hanging beside a leader.
    marks = sorted((p for p in peaks if p.time is not None), key=lambda p: p.time)
    ax.set_ylim(lo, hi_data + 100)
    ticks = _alt_ticks(lo, hi_data, 500.0 if hi_data - lo <= 2500 else 1000.0)
    ax.set_yticks(ticks)
    ax.set_yticklabels([loc.num(v) for v in ticks])
    labels = []
    for p in marks:
        x = mdates.date2num(p.time.replace(tzinfo=None))
        name = ax.annotate(p.name, (x, hi_data), xytext=(0, 0), textcoords="offset points",
                           ha="right", va="bottom", fontproperties=fonts.muted, color=c["ink-muted"],
                           zorder=6, path_effects=_halo(c["surface-000"]))
        num = ax.annotate(loc.metres(p.elevation_m), (x, hi_data), xytext=(0, 11),
                          textcoords="offset points", ha="right", va="bottom",
                          fontproperties=fonts.peak, color=c["ink"], zorder=6,
                          path_effects=_halo(c["surface-000"]))
        labels.append((p, x, name, num))
    # rest labels: horizontal, centred on their grey band, in a strip at the top of the plot
    rest_texts = []
    for i, (a, b) in enumerate(rest_spans):
        name = rest_labels[i] if rest_labels and i < len(rest_labels) else None
        if name or (b - a) > dt.timedelta(hours=5):
            a_, b_ = a.replace(tzinfo=None), b.replace(tzinfo=None)
            rest_texts.append(ax.annotate(
                name or loc.ui("night"), (mdates.date2num(a_ + (b_ - a_) / 2), 1.0),
                xycoords=("data", "axes fraction"), xytext=(0, -3), textcoords="offset points",
                ha="center", va="top", fontproperties=fonts.muted, color=c["ink-muted"], zorder=4,
                path_effects=_halo(c["surface-200"], 2.5)))
    fig.subplots_adjust(left=0.075, right=0.995, top=0.99, bottom=0.1)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    geometry = [(ax.transData.transform((x, 0))[0],
                 max(name.get_window_extent(renderer).width, num.get_window_extent(renderer).width))
                for _, x, name, num in labels]
    slots = _flag_layout(geometry, ax.bbox.x0)
    placed = [(*lab, row, side) for lab, (row, side) in zip(labels, slots, strict=True)]
    n_rows = max((row for row, _ in slots), default=0) + 1
    row_h, gap = 28.0, 14.0                      # points: height of one label row, dot-to-label gap
    # rest labels sit in a strip above the summit labels, one row more for each set that would overlap
    strip_rows = _strip_rows([(r.get_window_extent(renderer).x0, r.get_window_extent(renderer).x1)
                              for r in rest_texts])
    strip_pts = (max(strip_rows) + 1) * 12.0 + 2 if rest_texts else 0.0
    head_pts = gap + n_rows * row_h + 4 + strip_pts   # headroom needed above the highest data point
    axes_pts = ax.bbox.height * 72 / fig.dpi
    span = (hi_data - lo) / (1 - head_pts / axes_pts)
    ax.set_ylim(lo, lo + span)
    pts_per_m = axes_pts / span
    for p, x, name, num, row, side in placed:
        y_label = hi_data + (gap + row * row_h) / pts_per_m
        off = -3 if side == "right" else 3
        for ann, dy in ((name, 0), (num, 11)):
            ann.xy = (x, y_label)
            ann.set_position((off, dy))
            ann.set_ha(side)
        ax.plot([x, x], [p.elevation_m + 30, y_label - 2 / pts_per_m], color=c["line-strong"], lw=0.5,
                zorder=4)
        ax.plot([x], [p.elevation_m], marker="o", ms=6 * PX, mfc=c["surface-000"],
                mec=c["series-1"], mew=2 * PX, zorder=5)

    # Axes: ISO day labels centred on each day, hairlines at midnight, rests labelled.
    labelled, midnights = _day_axis(naive[0], naive[-1])
    ax.set_xticks([mdates.date2num(c) for _, c in labelled])
    ax.set_xticklabels([loc.short_date(d) for d, _ in labelled])
    # midnight lines stop at the highest point, below the summit labels
    ax.vlines([mdates.date2num(m) for m in midnights], lo, hi_data, color=c["line-strong"], lw=0.4,
              zorder=2.5)
    _style_cartesian(ax, theme, fonts)
    ax.spines["bottom"].set_visible(True)
    for text, row in zip(rest_texts, strip_rows, strict=True):
        text.set_position((0, -3 - row * 12.0))

    fig.savefig(out, format="svg")
    plt.close(fig)
    return height_in / width_in


# --------------------------------------------------------------------------------------------
# Climb high, sleep low
# --------------------------------------------------------------------------------------------

def acclimatisation_chart(
    days: list[DayPoint],
    summit: tuple[str, float, int] | None,
    theme: dict,
    loc: Locale,
    out: Path,
) -> float:
    """The day's high point (orange, filled) against the altitude slept at (blue, line only).

    ``summit`` is (name, altitude, day index) of the highest point, called out with a hollow dot.
    """
    fonts = setup_style(theme)
    c = theme["colors"]
    width_in = text_width_mm(theme) * MM
    height_in = width_in * 0.42
    fig, ax = plt.subplots(figsize=(width_in, height_in))

    x = np.arange(len(days))
    high = np.array([d.high_m for d in days])
    sleep_idx = [i for i, d in enumerate(days) if d.sleep_m is not None]
    sleep = np.array([days[i].sleep_m for i in sleep_idx])
    all_vals = np.concatenate([high, sleep])
    lo = _round_floor(all_vals.min() - 100, 500)
    top_val = float(all_vals.max())
    step = 500.0 if top_val - lo <= 2500 else 1000.0
    ticks = _alt_ticks(lo, top_val, step)

    ax.fill_between(x, high, lo, color=c["chart-area"], lw=0, zorder=2)
    ax.plot(x, high, color=c["series-1"], lw=2 * PX, zorder=3)
    ax.plot(sleep_idx, sleep, color=c["series-2"], lw=2 * PX, zorder=3)
    ax.set_xlim(-0.35, len(days) - 1 + 0.35)
    ax.set_ylim(lo, top_val + (top_val - lo) * 0.16)
    ax.set_yticks(ticks)
    ax.set_yticklabels([loc.num(v) for v in ticks])
    ax.set_xticks(x)
    ax.set_xticklabels([d.label for d in days])

    # direct labels at the right end of each line, in the series colour
    ax.annotate(loc.ui("acc_high"), (x[-1], high[-1]), xytext=(8, 0), textcoords="offset points",
                va="center", fontproperties=fonts.sans_semibold, color=c["accent-text"],
                annotation_clip=False)
    if sleep_idx:
        ax.annotate(loc.ui("acc_sleep"), (sleep_idx[-1], sleep[-1]), xytext=(8, 0),
                    textcoords="offset points", va="center", fontproperties=fonts.sans_semibold,
                    color=c["series-2"], annotation_clip=False)
    if summit:
        name, alt, i = summit
        ax.plot([i], [high[i]], marker="o", ms=6 * PX, mfc=c["surface-000"], mec=c["series-1"],
                mew=2 * PX, zorder=5)
        ax.annotate(f"{loc.metres(alt)}", (i, high[i]), xytext=(0, 8), textcoords="offset points",
                    ha="center", va="bottom", fontproperties=fonts.peak, color=c["ink"],
                    path_effects=_halo(c["surface-000"]), zorder=6)
        ax.annotate(name, (i, high[i]), xytext=(0, 22), textcoords="offset points", ha="center",
                    va="bottom", fontproperties=fonts.muted, color=c["ink-muted"],
                    path_effects=_halo(c["surface-000"]), zorder=6)

    _style_cartesian(ax, theme, fonts)
    ax.spines["bottom"].set_visible(True)
    fig.subplots_adjust(left=0.075, right=0.80, top=0.97, bottom=0.12)
    fig.savefig(out, format="svg")
    plt.close(fig)
    return height_in / width_in


def day_filled(day: AltDay, base_m: float) -> bool:
    """Whether a day counts as the way up (orange) rather than the way down (grey): it ended at least as
    high as it started, except a day that never left base camp."""
    if day.high_m - day.low_m < 1 and day.close_m <= base_m:
        return False
    return day.close_m >= day.open_m


def altitude_chart(
    days: list[AltDay],
    summits: list[tuple[str, float, int]],
    base_m: float,
    theme: dict,
    loc: Locale,
    out: Path,
) -> float:
    """The whole stay above base camp, one bar per day. Returns height/width.

    A bar runs from the day's lowest to its highest point, without a border: shaded like the area under
    an elevation profile when ``day_filled`` (the way up), in the grey of the profile's night bands
    otherwise (the way down). A day spent in one place has no bar. A thick line marks each night at
    its altitude and a thin line joins the nights from day to day. ``summits`` holds (name, official
    altitude, day index); each is called out above its day.
    """
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle

    fonts = setup_style(theme)
    c = theme["colors"]
    width_in = text_width_mm(theme) * MM
    height_in = width_in * 0.62      # it has a page of its own
    fig, ax = plt.subplots(figsize=(width_in, height_in))

    low = np.array([d.low_m for d in days])
    high = np.array([d.high_m for d in days])
    lo = _round_floor(low.min() - 100, 500)
    top = float(high.max())
    step = 500.0 if top - lo <= 2500 else 1000.0
    ticks = _alt_ticks(lo, top, step)
    bar_w, night_lw = 0.62, 2.6 * PX * 1.3
    min_h = (top - lo) * 0.012          # less than this: the day was spent in one place

    for i, d in enumerate(days):
        if d.high_m - d.low_m >= min_h:   # a day spent in one place has no bar, only its night
            ax.add_patch(Rectangle((i - bar_w / 2, d.low_m), bar_w, d.high_m - d.low_m, lw=0, zorder=3,
                                   facecolor=c["chart-area"] if day_filled(d, base_m) else c["surface-200"]))
        if d.night_m is not None:
            ax.plot([i - bar_w / 2, i + bar_w / 2], [d.night_m] * 2, color=c["series-1"], lw=night_lw,
                    solid_capstyle="butt", zorder=4)

    # a thin line joins the nights from bar to bar, so their progression reads at a glance
    path = [(x, d.night_m) for i, d in enumerate(days) if d.night_m is not None
            for x in (i - bar_w / 2, i + bar_w / 2)]
    if path:
        px, py = zip(*path, strict=True)
        ax.plot(px, py, color=c["series-1"], lw=0.9 * PX * 1.3, solid_joinstyle="round", zorder=4)

    head = 0.22 if summits else 0.12       # room above for the summit labels and the key
    ax.set_xlim(-0.7, len(days) - 0.3)
    ax.set_ylim(lo, top + (top - lo) * head)
    ax.set_yticks(ticks)
    ax.set_yticklabels([loc.num(v) for v in ticks])

    # ISO dates, as many as fit: every day, or every second, third ... day
    every = max(1, math.ceil(len(days) / 7))
    shown = list(range(0, len(days), every))
    ax.set_xticks(shown)
    ax.set_xticklabels([loc.short_date(days[i].date) for i in shown])

    for name, alt, i in summits:
        ax.annotate(loc.metres(alt), (i, high[i]), xytext=(0, 18), textcoords="offset points",
                    ha="center", va="bottom", fontproperties=fonts.peak, color=c["ink"],
                    path_effects=_halo(c["surface-000"]), zorder=6, annotation_clip=False)
        ax.annotate(name, (i, high[i]), xytext=(0, 5), textcoords="offset points", ha="center",
                    va="bottom", fontproperties=fonts.muted, color=c["ink-muted"],
                    path_effects=_halo(c["surface-000"]), zorder=6, annotation_clip=False)

    key = [Rectangle((0, 0), 1, 1, facecolor=c["chart-area"], lw=0),
           Rectangle((0, 0), 1, 1, facecolor=c["surface-200"], lw=0),
           Line2D([], [], color=c["series-1"], lw=night_lw, solid_capstyle="butt")]
    legend = ax.legend(key, [loc.ui("alt_up"), loc.ui("alt_down"), loc.ui("acc_sleep")], loc="upper left",
                       frameon=False, prop=fonts.muted, handlelength=1.4, handleheight=0.9,
                       borderaxespad=0.2, labelspacing=0.35)
    for t in legend.get_texts():
        t.set_color(c["ink-muted"])

    _style_cartesian(ax, theme, fonts)
    ax.spines["bottom"].set_visible(True)
    fig.subplots_adjust(left=0.075, right=0.995, top=0.98, bottom=0.08)
    fig.savefig(out, format="svg")
    plt.close(fig)
    return height_in / width_in


# --------------------------------------------------------------------------------------------
# Route map
# --------------------------------------------------------------------------------------------

def _merc(lat, lon):
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    x = R_MERC * np.radians(lon)
    y = R_MERC * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
    return x, y


def _nice_step(span_m: float) -> float:
    target = span_m / 4
    mag = 10 ** math.floor(math.log10(target))
    for m in (1, 2, 5, 10):
        if m * mag >= target:
            return m * mag
    return 10 * mag


MAP_RATIO = 0.62  # height/width; the map shares its page with the elevation profile, so it cannot be taller


@dataclass
class MapView:
    """What the route map shows: decimated track in web mercator and the visible window."""

    x: np.ndarray
    y: np.ndarray
    keep: np.ndarray            # indices of the track points kept
    xlim: tuple[float, float]
    ylim: tuple[float, float]
    ratio: float                # figure height / width

    @property
    def extent(self) -> tuple[float, float, float, float]:
        return (*self.xlim, *self.ylim)


def map_view(track: Track) -> MapView:
    """Decimate the track to ~15 m spacing and choose the visible window around it."""
    keep = [0]
    for i in range(1, len(track)):
        if track.dist[i] - track.dist[keep[-1]] >= 15:
            keep.append(i)
    if keep[-1] != len(track) - 1:
        keep.append(len(track) - 1)
    keep_arr = np.array(keep)
    x, y = _merc(track.lat[keep_arr], track.lon[keep_arr])
    pad = 0.12
    xmin, xmax, ymin, ymax = x.min(), x.max(), y.min(), y.max()
    dx, dy = max(xmax - xmin, 500), max(ymax - ymin, 500)
    ratio = MAP_RATIO
    cx_, cy_ = (xmin + xmax) / 2, (ymin + ymax) / 2
    half_w = dx * (0.5 + pad)
    half_h = max(dy * (0.5 + pad), half_w * ratio)
    half_w = max(half_w, half_h / ratio)
    return MapView(x, y, keep_arr, (cx_ - half_w, cx_ + half_w), (cy_ - half_h, cy_ + half_h), ratio)


def route_map(
    track: Track,
    day_starts: list[int],
    peaks: list[PeakMark],
    theme: dict,
    loc: Locale,
    out: Path,
    color_by: str = "none",
    label_peaks: bool = True,
    base_image=None,
    base_out: Path | None = None,
) -> float:
    """Route on a map; returns height/width ratio of the figure.

    With ``base_image`` (a PIL image already cropped to the map window) the SVG is transparent
    and the image is written to ``base_out`` to be placed underneath; otherwise a flat grid is
    drawn in the SVG itself.
    """
    fonts = setup_style(theme)
    c = theme["colors"]
    width_in = text_width_mm(theme) * MM
    view = map_view(track)
    keep_arr, x, y, ratio = view.keep, view.x, view.y, view.ratio
    cx_, cy_ = sum(view.xlim) / 2, sum(view.ylim) / 2
    half_w, half_h = (view.xlim[1] - view.xlim[0]) / 2, (view.ylim[1] - view.ylim[0]) / 2
    fig, ax = plt.subplots(figsize=(width_in, width_in * ratio))
    ax.set_xlim(*view.xlim)
    ax.set_ylim(*view.ylim)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor(c["surface-100"])

    lat0 = float(np.mean(track.lat))
    k = 1 / math.cos(math.radians(lat0))  # mercator metres per true metre
    if base_image is not None:
        base_image.save(base_out, quality=88, optimize=True)
        ax.set_facecolor("none")
        fig.patch.set_alpha(0)
    else:
        step = _nice_step(2 * half_w / k) * k
        for v in np.arange(math.floor((cx_ - half_w) / step) * step, cx_ + half_w + step, step):
            ax.axvline(v, color=c["line"], lw=0.75, zorder=0)
        for v in np.arange(math.floor((cy_ - half_h) / step) * step, cy_ + half_h + step, step):
            ax.axhline(v, color=c["line"], lw=0.75, zorder=0)

    ax.plot(x, y, color=c["surface-000"], lw=4 * PX * 1.6, solid_joinstyle="round", zorder=3)
    if color_by == "day" and len(day_starts) > 1:
        cycle = [c[f"series-{i}"] for i in range(1, 6)]
        bounds = [int(np.searchsorted(keep_arr, s)) for s in day_starts] + [len(keep_arr)]
        for i in range(len(day_starts)):
            a, b = bounds[i], min(bounds[i + 1] + 1, len(keep_arr))
            ax.plot(x[a:b], y[a:b], color=cycle[i % len(cycle)], lw=2 * PX * 1.3,
                    solid_joinstyle="round", zorder=4)
    else:
        ax.plot(x, y, color=c["series-1"], lw=2 * PX * 1.3, solid_joinstyle="round", zorder=4)

    badges = []
    pt = 2 * half_w / (width_in * 72)    # data units per point
    for n, s in enumerate(day_starts, start=1):
        bx, by = _merc(track.lat[s], track.lon[s])
        # a day starting where another did (back at the same camp) sits beside it, not under it
        while any(math.hypot(bx - ox, by - oy) < 11 * pt for ox, oy in badges):
            bx += 12 * pt
        ax.plot([bx], [by], marker="o", ms=11, mfc=c["surface-inverse"], mec=c["surface-000"],
                mew=1.2, zorder=7)
        ax.text(bx, by, str(n), color=c["ink-inverse"], fontproperties=fonts.tick, ha="center",
                va="center", zorder=8)
        badges.append((float(bx), float(by)))

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    occupied = []
    for bx, by in badges:
        px, py = ax.transData.transform((bx, by))
        occupied.append((px - 9, py - 9, px + 9, py + 9))
    candidates = [(6, 5, "left", "bottom"), (6, -5, "left", "top"), (-6, 5, "right", "bottom"),
                  (-6, -5, "right", "top"), (0, 8, "center", "bottom"), (0, -8, "center", "top"),
                  (9, 0, "left", "center"), (-9, 0, "right", "center")]

    def put(p, ox, oy, ha, va):
        return ax.annotate(p.name, _merc(p.lat, p.lon), xytext=(ox, oy), textcoords="offset points",
                           ha=ha, va=va, fontproperties=fonts.sans, color=c["ink"], zorder=9,
                           path_effects=_halo(c["surface-100"]))

    dots = {}
    for p in peaks:   # keep every summit dot clear of the other summits' labels
        if p.lat is not None and p.lon is not None:
            px, py = ax.transData.transform(_merc(p.lat, p.lon))
            dots[p.name] = (px, py)
            occupied.append((px - 4, py - 4, px + 4, py + 4))
    clear_px = 8 * fig.dpi / 72   # wanted gap between a label and another summit's dot

    def clearance(name: str, box: tuple) -> float:
        gaps = [math.hypot(max(box[0] - x, 0, x - box[2]), max(box[1] - y, 0, y - box[3]))
                for n, (x, y) in dots.items() if n != name]
        return min(gaps, default=math.inf)

    for p in peaks:
        if p.lat is None or p.lon is None:
            continue
        px_, py_ = _merc(p.lat, p.lon)
        ax.plot([px_], [py_], marker="o", ms=6 * PX * 1.2, mfc=c["surface-000"], mec=c["ink"],
                mew=2 * PX, zorder=6)
        if not label_peaks:
            continue
        # the first free spot well clear of the other summits, else the free spot farthest from them
        best, best_gap = None, -1.0
        for spot in candidates:
            txt = put(p, *spot)
            fig.canvas.draw()
            bb = txt.get_window_extent(renderer)
            txt.remove()
            box = (bb.x0, bb.y0, bb.x1, bb.y1)
            hit = any(not (box[2] < o[0] or box[0] > o[2] or box[3] < o[1] or box[1] > o[3])
                      for o in occupied)
            inside = (ax.bbox.x0 <= box[0] and box[2] <= ax.bbox.x1 and
                      ax.bbox.y0 <= box[1] and box[3] <= ax.bbox.y1)
            if hit or not inside:
                continue
            gap = clearance(p.name, box)
            if gap > best_gap:
                best, best_gap = spot, gap
            if gap >= clear_px:
                break
        txt = put(p, *(best or candidates[0]))   # no free spot: fall back to the first candidate
        fig.canvas.draw()
        bb = txt.get_window_extent(renderer)
        best = (bb.x0, bb.y0, bb.x1, bb.y1)
        occupied.append(best)

    bar_true = _nice_step(2 * half_w / k) / 2
    bx0, by0 = cx_ - half_w + half_w * 0.06, cy_ - half_h + half_h * 0.08
    ax.plot([bx0, bx0 + bar_true * k], [by0, by0], color=c["ink"], lw=1.5, solid_capstyle="butt", zorder=9)
    label = f"{bar_true / 1000:g} {loc.ui('kilometers')}" if bar_true >= 1000 else f"{bar_true:g} {loc.ui('meters')}"
    ax.text(bx0, by0 + half_h * 0.03, label, fontproperties=fonts.tick, va="bottom", ha="left",
            color=c["ink"], zorder=9, path_effects=_halo(c["surface-100"]))
    nx, ny = cx_ + half_w * 0.93, cy_ + half_h * 0.80
    ax.annotate("", xy=(nx, ny + half_h * 0.10), xytext=(nx, ny), zorder=9,
                arrowprops=dict(arrowstyle="-|>", color=c["ink"], lw=1.0, mutation_scale=7))
    ax.text(nx, ny + half_h * 0.13, loc.ui("north"), ha="center", va="bottom",
            fontproperties=fonts.peak, color=c["ink"], zorder=9)

    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(out, format="svg", transparent=base_image is not None)
    plt.close(fig)
    return ratio
