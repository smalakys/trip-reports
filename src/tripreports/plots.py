"""Figures: the route map and the elevation profile. Plain inputs in, an SVG file out."""

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

from .gpxstats import Track  # noqa: E402
from .i18n import Locale  # noqa: E402
from .theme import FONTS_DIR, text_width_mm  # noqa: E402

MM = 1 / 25.4
R_MERC = 6_378_137.0


@dataclass
class PeakMark:
    name: str
    elevation_m: float
    time: dt.datetime | None  # local time of the summit, if known
    lat: float | None = None
    lon: float | None = None


def setup_style(theme: dict) -> None:
    for ttf in FONTS_DIR.glob("*.ttf"):
        font_manager.fontManager.addfont(str(ttf))
    c = theme["colors"]
    plt.rcParams.update({
        "svg.fonttype": "path",
        "font.family": theme["fonts"]["family"],
        "font.size": 7.5,
        "text.color": c["ink"],
        "axes.edgecolor": c["rule"],
        "axes.labelcolor": c["muted"],
        "xtick.color": c["muted"],
        "ytick.color": c["muted"],
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.spines.bottom": False,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })


def _halo(color="white", w=2.5):
    return [pe.withStroke(linewidth=w, foreground=color)]


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
) -> float:
    """Draw the profile; returns height/width ratio of the figure."""
    setup_style(theme)
    c = theme["colors"]
    width_in = text_width_mm(theme) * MM
    height_in = width_in * 0.46
    fig, ax = plt.subplots(figsize=(width_in, height_in))

    naive = [x.replace(tzinfo=None) for x in track.t]
    t = mdates.date2num(naive)
    ele = track.ele

    for a, b in rest_spans:
        ax.axvspan(mdates.date2num(a.replace(tzinfo=None)), mdates.date2num(b.replace(tzinfo=None)),
                   color=c["surface"], lw=0, zorder=0)
    ax.fill_between(t, ele, 0, color=c["accent"], alpha=0.10, lw=0, zorder=2)
    ax.plot(t, ele, color=c["accent"], lw=1.3, zorder=3, solid_capstyle="round")

    lo = math.floor((ele.min() - 150) / 500) * 500
    hi_data = ele.max()
    ax.set_xlim(t[0], t[-1])

    # Summit labels: staggered rows above the profile, with leader lines.
    marks = [p for p in peaks if p.time is not None]
    marks.sort(key=lambda p: p.time)
    labels = []
    for p in marks:
        x = mdates.date2num(p.time.replace(tzinfo=None))
        txt = ax.text(x, 0, f"{p.name}\n{loc.metres(p.elevation_m)}", ha="right", va="bottom", multialignment="right",
                      fontsize=6.3, linespacing=1.25, color=c["ink"], zorder=6,
                      path_effects=_halo("white", 3.0))
        labels.append((p, x, txt))
    ax.set_ylim(lo, hi_data + 100)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    # Greedy row assignment: labels in one row must not overlap, and a leader line must not cross
    # a label in a lower row (or be crossed by one placed later).
    items: list[tuple[float, float, float, int]] = []  # x0, x1, leader x, row (pixels)
    placed = []
    inv = ax.transData.inverted()
    for p, x, txt in labels:
        bb = txt.get_window_extent(renderer)
        w = bb.x1 - bb.x0
        xc = ax.transData.transform((x, 0))[0]  # the leader's x

        row, side = _flag_slot(items, xc, w, ax.bbox.x0)
        x0, x1 = (xc - w - 3, xc + 3) if side == "right" else (xc - 3, xc + w + 3)
        items.append((x0, x1, xc, row))
        placed.append((p, x, txt, row, side))
    row_end = [0] * (max((r for *_, r in items), default=-1) + 1)
    n_rows = len(row_end)
    row_h = (hi_data - lo) * 0.19
    top = hi_data + 120 + row_h * max(n_rows, 1)
    ax.set_ylim(lo, top)
    pad = inv.transform((ax.transData.transform((t[0], 0))[0] + 3, 0))[0] - t[0]
    for p, x, txt, row, side in placed:
        y_label = hi_data + 140 + row * row_h
        txt.set_position((x - pad if side == "right" else x + pad, y_label))
        txt.set_ha("right" if side == "right" else "left")
        txt.set_multialignment("right" if side == "right" else "left")
        ax.plot([x, x], [p.elevation_m + 25, y_label - 12], color=c["muted"], lw=0.5, zorder=4)
        ax.plot([x], [p.elevation_m], marker="o", ms=3.4, mfc="white", mec=c["ink"], mew=0.9, zorder=5)

    # Axes: day names centred on each day, hairline at midnight, horizontal grid.
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
    for d in days[1:]:
        ax.axvline(mdates.date2num(dt.datetime.combine(d, dt.time(0))), color=c["rule"], lw=0.6, zorder=1)
    ax.tick_params(axis="x", length=0, pad=5)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.yaxis.grid(True, color=c["rule"], lw=0.5)
    ax.set_axisbelow(True)
    ticks = [v for v in np.arange(lo, hi_data + 1, 500) if v <= hi_data + 50]
    ax.set_yticks(ticks)
    ax.set_yticklabels([loc.num(v) for v in ticks])

    for a, b in rest_spans:
        mid = mdates.date2num(a.replace(tzinfo=None)) + (mdates.date2num(b.replace(tzinfo=None)) -
                                                          mdates.date2num(a.replace(tzinfo=None))) / 2
        if (b - a) > dt.timedelta(hours=5):
            ax.text(mid, lo + (hi_data - lo) * 0.02, loc.ui("night"), rotation=90, ha="center",
                    va="bottom", fontsize=6, color=c["muted"], zorder=1)

    fig.subplots_adjust(left=0.065, right=0.995, top=0.99, bottom=0.09)
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


def route_map(
    track: Track,
    day_starts: list[int],
    peaks: list[PeakMark],
    theme: dict,
    loc: Locale,
    out: Path,
    basemap: str = "plain",
    color_by: str = "none",
    label_peaks: bool = True,
) -> float:
    """Draw the route map; returns height/width ratio of the figure."""
    setup_style(theme)
    c = theme["colors"]
    width_in = text_width_mm(theme) * MM

    # decimate to ~15 m spacing for a light SVG
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
    fig, ax = plt.subplots(figsize=(width_in, width_in * ratio))
    cx_, cy_ = (xmin + xmax) / 2, (ymin + ymax) / 2
    half_w = dx * (0.5 + pad)
    half_h = max(dy * (0.5 + pad), half_w * ratio)
    half_w = max(half_w, half_h / ratio)
    ax.set_xlim(cx_ - half_w, cx_ + half_w)
    ax.set_ylim(cy_ - half_h, cy_ + half_h)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor(c["surface"])

    lat0 = float(np.mean(track.lat))
    k = 1 / math.cos(math.radians(lat0))  # mercator metres per true metre
    if basemap == "tiles":
        try:
            import contextily as cx

            cx.add_basemap(ax, crs="EPSG:3857", source=cx.providers.CartoDB.PositronNoLabels,
                           attribution=False, zorder=0)
        except Exception as exc:  # network, missing extra, ...
            print(f"warning: map tiles unavailable ({exc}); using the plain basemap")
            basemap = "plain"
    if basemap == "plain":
        step = _nice_step(2 * half_w / k) * k
        gx = np.arange(math.floor((cx_ - half_w) / step) * step, cx_ + half_w + step, step)
        gy = np.arange(math.floor((cy_ - half_h) / step) * step, cy_ + half_h + step, step)
        for v in gx:
            ax.axvline(v, color="white", lw=0.8, zorder=0)
        for v in gy:
            ax.axhline(v, color="white", lw=0.8, zorder=0)

    # track
    ax.plot(x, y, color="white", lw=4.0, solid_capstyle="round", solid_joinstyle="round", zorder=3)
    if color_by == "day" and len(day_starts) > 1:
        bounds = [int(np.searchsorted(keep_arr, s)) for s in day_starts] + [len(keep_arr)]
        for i in range(len(day_starts)):
            a, b = bounds[i], min(bounds[i + 1] + 1, len(keep_arr))
            ax.plot(x[a:b], y[a:b], color=c["days"][i % len(c["days"])], lw=2.0,
                    solid_capstyle="round", solid_joinstyle="round", zorder=4)
    else:
        ax.plot(x, y, color=c["accent"], lw=2.0, solid_capstyle="round", solid_joinstyle="round", zorder=4)

    # day-start badges
    badges = []
    for n, s in enumerate(day_starts, start=1):
        bx, by = _merc(track.lat[s], track.lon[s])
        ax.plot([bx], [by], marker="o", ms=9.5, mfc=c["ink"], mec="white", mew=1.2, zorder=7)
        ax.text(bx, by, str(n), color="white", fontsize=5.8, fontweight="bold", ha="center",
                va="center", zorder=8)
        badges.append((float(bx), float(by)))

    # peaks with collision-aware labels
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    occupied = []
    for bx, by in badges:
        px, py = ax.transData.transform((bx, by))
        occupied.append((px - 8, py - 8, px + 8, py + 8))
    candidates = [(6, 5, "left", "bottom"), (6, -5, "left", "top"), (-6, 5, "right", "bottom"),
                  (-6, -5, "right", "top"), (0, 8, "center", "bottom"), (0, -8, "center", "top"),
                  (9, 0, "left", "center"), (-9, 0, "right", "center")]
    for p in peaks:
        if p.lat is None or p.lon is None:
            continue
        px_, py_ = _merc(p.lat, p.lon)
        ax.plot([px_], [py_], marker="^", ms=5.2, mfc=c["ink"], mec="white", mew=0.8, zorder=6)
        if not label_peaks:
            continue
        best = None
        for ox, oy, ha, va in candidates:
            txt = ax.annotate(p.name, (px_, py_), xytext=(ox, oy), textcoords="offset points",
                              ha=ha, va=va, fontsize=6.3, color=c["ink"], zorder=9,
                              path_effects=_halo())
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
            ox, oy, ha, va = candidates[0]
            txt = ax.annotate(p.name, (px_, py_), xytext=(ox, oy), textcoords="offset points",
                              ha=ha, va=va, fontsize=6.3, color=c["ink"], zorder=9,
                              path_effects=_halo())
            fig.canvas.draw()
            bb = txt.get_window_extent(renderer)
            best = (bb.x0, bb.y0, bb.x1, bb.y1)
        occupied.append(best)

    # scale bar and north arrow
    bar_true = _nice_step(2 * half_w / k) / 2
    bar_true = {500: 500, 1000: 1000}.get(bar_true, bar_true)
    bx0, by0 = cx_ - half_w + half_w * 0.06, cy_ - half_h + half_h * 0.08
    ax.plot([bx0, bx0 + bar_true * k], [by0, by0], color=c["ink"], lw=1.6, solid_capstyle="butt", zorder=9)
    label = f"{bar_true / 1000:g} {loc.ui('kilometers')}" if bar_true >= 1000 else f"{bar_true:g} {loc.ui('meters')}"
    ax.text(bx0, by0 + half_h * 0.03, label, fontsize=6.3, va="bottom", ha="left", color=c["ink"],
            zorder=9, path_effects=_halo())
    nx, ny = cx_ + half_w * 0.93, cy_ + half_h * 0.80
    ax.annotate("", xy=(nx, ny + half_h * 0.10), xytext=(nx, ny), zorder=9,
                arrowprops=dict(arrowstyle="-|>", color=c["ink"], lw=1.0, mutation_scale=7))
    ax.text(nx, ny + half_h * 0.13, loc.ui("north"), ha="center", va="bottom", fontsize=6.5,
            fontweight="bold", color=c["ink"], zorder=9)

    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(out, format="svg")
    plt.close(fig)
    return ratio
