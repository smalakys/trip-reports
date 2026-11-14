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

def _flag_slot(items: list[tuple[float, float, float, int]], xc: float, w: float,
               left_limit: float) -> tuple[int, str]:
    """Choose a row and side for a label hanging beside a vertical leader at pixel ``xc``.

    ``items`` holds the already placed labels as (x0, x1, leader x, row). Labels in one row must
    not overlap and leaders must not cross labels; if no clean spot exists, only overlaps within
    a row are avoided. Returns (row, side) with side "right" (label left of leader) or "left".
    """

    def box(side: str) -> tuple[float, float]:
        return (xc - w - 3, xc + 3) if side == "right" else (xc - 3, xc + w + 3)

    def clashes(row: int, side: str, strict: bool) -> bool:
        x0, x1 = box(side)
        for ox0, ox1, oxc, orow in items:
            if orow == row and not (x1 < ox0 or x0 > ox1):
                return True
            if strict and orow < row and ox0 <= xc <= ox1:   # our leader crosses that label
                return True
            if strict and orow > row and x0 <= oxc <= x1:    # their leader crosses our label
                return True
        return False

    sides = ["right", "left"] if xc - w - 3 > left_limit else ["left", "right"]
    for row in range(6):
        for side in sides:
            if not clashes(row, side, True):
                return row, side
    return next(r for r in range(64) if not clashes(r, sides[0], False)), sides[0]


# --------------------------------------------------------------------------------------------
# Elevation profile
# --------------------------------------------------------------------------------------------

def elevation_profile(
    track: Track,
    rest_spans: list[tuple[dt.datetime, dt.datetime]],
    peaks: list[PeakMark],
    theme: dict,
    loc: Locale,
    out: Path,
    rest_labels: list[str | None] | None = None,
) -> float:
    """Altitude against time, filled to the baseline, summits called out. Returns height/width.

    ``rest_labels`` names each rest span (for example the hut slept at); a span without a name
    is labelled with the generic word for night.
    """
    fonts = setup_style(theme)
    c = theme["colors"]
    width_in = text_width_mm(theme) * MM
    height_in = width_in * 0.44
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
    fig.subplots_adjust(left=0.075, right=0.995, top=0.99, bottom=0.1)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    items: list[tuple[float, float, float, int]] = []
    placed = []
    for p, x, name, num in labels:
        w = max(name.get_window_extent(renderer).width, num.get_window_extent(renderer).width)
        xc = ax.transData.transform((x, 0))[0]
        row, side = _flag_slot(items, xc, w, ax.bbox.x0)
        x0, x1 = (xc - w - 3, xc + 3) if side == "right" else (xc - 3, xc + w + 3)
        items.append((x0, x1, xc, row))
        placed.append((p, x, name, num, row, side))
    n_rows = max((r for *_, r in items), default=0) + 1
    row_h, gap = 28.0, 14.0                      # points: height of one label row, dot-to-label gap
    head_pts = gap + n_rows * row_h + 4          # headroom needed above the highest data point
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
    days = sorted({x.date() for x in naive})
    t0, t1 = naive[0], naive[-1]
    centres, names = [], []
    for d in days:
        lo_t = max(dt.datetime.combine(d, dt.time(0)), t0)
        hi_t = min(dt.datetime.combine(d, dt.time(0)) + dt.timedelta(days=1), t1)
        if hi_t - lo_t >= dt.timedelta(hours=4):
            centres.append(mdates.date2num(lo_t) + (mdates.date2num(hi_t) - mdates.date2num(lo_t)) / 2)
            names.append(loc.short_date(d))
    ax.set_xticks(centres)
    ax.set_xticklabels(names)
    _style_cartesian(ax, theme, fonts)
    ax.spines["bottom"].set_visible(True)
    for i, (a, b) in enumerate(rest_spans):
        name = rest_labels[i] if rest_labels and i < len(rest_labels) else None
        if name or (b - a) > dt.timedelta(hours=5):
            mid = mdates.date2num(a.replace(tzinfo=None)) + (
                mdates.date2num(b.replace(tzinfo=None)) - mdates.date2num(a.replace(tzinfo=None))) / 2
            ax.text(mid, lo + (hi_data - lo) * 0.02, name or loc.ui("night"), rotation=90, ha="center",
                    va="bottom", fontproperties=fonts.muted, color=c["ink-muted"], zorder=4,
                    path_effects=_halo(c["surface-200"], 2.5))

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
    ratio = min(max(dy / dx, 0.62), 1.1)
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
    for n, s in enumerate(day_starts, start=1):
        bx, by = _merc(track.lat[s], track.lon[s])
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

    for p in peaks:
        if p.lat is None or p.lon is None:
            continue
        px_, py_ = _merc(p.lat, p.lon)
        ax.plot([px_], [py_], marker="o", ms=6 * PX * 1.2, mfc=c["surface-000"], mec=c["ink"],
                mew=2 * PX, zorder=6)
        if not label_peaks:
            continue
        best = None
        for ox, oy, ha, va in candidates:
            txt = put(p, ox, oy, ha, va)
            fig.canvas.draw()
            bb = txt.get_window_extent(renderer)
            box = (bb.x0, bb.y0, bb.x1, bb.y1)
            hit = any(not (box[2] < o[0] or box[0] > o[2] or box[3] < o[1] or box[1] > o[3])
                      for o in occupied)
            inside = (ax.bbox.x0 <= box[0] and box[2] <= ax.bbox.x1 and
                      ax.bbox.y0 <= box[1] and box[3] <= ax.bbox.y1)
            if not hit and inside:
                best = box
                break
            txt.remove()
        if best is None:  # no free spot: fall back to the first candidate
            txt = put(p, *candidates[0])
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
