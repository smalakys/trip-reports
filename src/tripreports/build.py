"""The build pipeline: trip folder -> prepared assets -> figures -> document model -> ReportLab -> PDF."""

from __future__ import annotations

import datetime as dt
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import plots
from .analysis import Analysis, acclimatisation_points, analyse
from .document import Assets, GroupFigures, build_document
from .i18n import Locale
from .images import prepare_image
from .render import render_pdf
from .schema import Trip, load_trip
from .theme import load_theme


@dataclass
class BuildResult:
    pdf: Path
    build_dir: Path
    analysis: Analysis
    warnings: list[str] = field(default_factory=list)
    pngs: list[Path] = field(default_factory=list)


def _check_files(trip: Trip, trip_dir: Path) -> None:
    missing = [p for p in [*(f.file for f in trip.gpx_files()), trip.cover.image, *(ph.file for ph in trip.photos)]
               if not (trip_dir / p).exists()]
    if missing:
        raise FileNotFoundError("files listed in the trip file are missing: " + ", ".join(missing))


def label_rests(trip: Trip, rest_spans) -> list[str | None]:
    """Name each rest: a night after the place slept at, a long daytime stop after a ``breaks`` entry.

    A night that starts after midnight belongs to the evening before.
    """
    sleep_at = {a.date: a.place for a in trip.accommodation}
    break_at = {b.date: b.place for b in trip.breaks}
    labels: list[str | None] = []
    for start, end in rest_spans:
        if end - start > dt.timedelta(hours=5):
            labels.append(sleep_at.get((start - dt.timedelta(hours=6)).date()))
        else:
            labels.append(break_at.get(start.date()))
    return labels


def build_report(
    trip_dir: str | Path,
    lang: str | None = None,
    out: str | Path | None = None,
    theme_path: str | Path | None = None,
    png_dir: str | Path | None = None,
    png_ppi: int = 70,
    mode: str | None = None,
    keep_build_dir: bool = True,
) -> BuildResult:
    trip, trip_dir = load_trip(trip_dir)
    lang = lang or trip.languages[0]
    Locale(lang)  # fail early for unsupported languages
    _check_files(trip, trip_dir)
    theme = load_theme(theme_path, mode=mode)
    out_pdf = Path(out) if out else trip_dir / "out" / f"report-{lang}.pdf"
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    build_dir = out_pdf.parent / f".build-{lang}"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    assets_dir = build_dir / "assets"
    assets_dir.mkdir(parents=True)

    # images
    img = theme["images"]
    cover_px = prepare_image(trip_dir / trip.cover.image, assets_dir / "cover.jpg",
                             img["cover_long_edge_px"], img["jpeg_quality"])
    photos = []
    for i, ph in enumerate(trip.photos, start=1):
        name = f"photo-{i:02d}.jpg"
        px = prepare_image(trip_dir / ph.file, assets_dir / name, img["photo_long_edge_px"],
                           img["jpeg_quality"])
        photos.append((f"assets/{name}", px))

    # analysis and figures
    an = analyse(trip, trip_dir)
    loc = Locale(lang)
    # (track, day starts, rests, peaks, file suffix): one map and profile per GPX file when there are several
    views = [(g.track, g.day_start_idx, g.rest_spans, g.peaks, f"-{i}") for i, g in enumerate(an.groups, start=1)] \
        or [(an.track, an.day_start_idx, an.rest_spans, an.peaks, "")]
    basemap, map_note = None, None
    if trip.map.basemap == "tiles":
        try:
            from .basemap import load_basemap

            exts = [plots.map_view(v[0]).extent for v in views]
            x0, x1 = min(e[0] for e in exts), max(e[1] for e in exts)
            y0, y1 = min(e[2] for e in exts), max(e[3] for e in exts)
            w, h = x1 - x0, y1 - y0
            wanted = (x0 - 0.05 * w, x1 + 0.05 * w, y0 - 0.05 * h, y1 + 0.05 * h)
            basemap = load_basemap(trip_dir, wanted, trip.map.tile_source)
            map_note = basemap.attribution
        except Exception as exc:  # no network, tiles blocked, missing [tiles] extra ...
            an.warnings.append(f"map tiles unavailable ({exc}); drew the plain map instead")
    figures = []
    for track, day_starts, rest_spans, peaks, sfx in views:
        base_image = None
        if basemap is not None:
            from .basemap import crop_and_tone

            base_image = crop_and_tone(basemap, plots.map_view(track).extent, desaturate=0.55, lighten=0.1)
        map_ratio = plots.route_map(track, day_starts, peaks, theme, loc, assets_dir / f"route-map{sfx}.svg",
                                    color_by=trip.map.color_by, label_peaks=trip.map.label_peaks,
                                    base_image=base_image, base_out=assets_dir / f"route-map-base{sfx}.jpg")
        prof_ratio = plots.elevation_profile(track, rest_spans, peaks, theme, loc,
                                             assets_dir / f"elevation-profile{sfx}.svg",
                                             rest_labels=label_rests(trip, rest_spans),
                                             # a lower profile leaves room for the group's heading
                                             height_ratio=0.35 if an.groups else 0.44)
        figures.append(GroupFigures(
            route_map=f"assets/route-map{sfx}.svg", route_map_ratio=map_ratio,
            route_map_under=f"assets/route-map-base{sfx}.jpg" if base_image is not None else None,
            profile=f"assets/elevation-profile{sfx}.svg", profile_ratio=prof_ratio))

    acc_file, acc_ratio, acc_delta = None, 0.0, 0.0
    if trip.acclimatisation_chart and len(an.days) >= 3:
        points, summit = acclimatisation_points(an, lambda n: f"{loc.ui('day')} {n}")
        gaps = [p.high_m - p.sleep_m for p in points if p.sleep_m is not None]
        acc_file, acc_delta = "assets/climb-high-sleep-low.svg", float(sum(gaps) / len(gaps))
        acc_ratio = plots.acclimatisation_chart(points, summit, theme, loc, assets_dir / "climb-high-sleep-low.svg")

    first = figures[0]
    assets = Assets(cover="assets/cover.jpg", cover_px=cover_px,
                    route_map=first.route_map, route_map_ratio=first.route_map_ratio,
                    route_map_under=first.route_map_under, map_attribution=map_note,
                    profile=first.profile, profile_ratio=first.profile_ratio,
                    acc=acc_file, acc_ratio=acc_ratio, acc_delta_m=acc_delta, photos=photos,
                    groups=figures if an.groups else [])
    doc = build_document(trip, an, assets, theme, lang)
    (build_dir / "data.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    render_pdf(doc, out_pdf, build_dir)

    pngs: list[Path] = []
    if png_dir:
        import pypdfium2 as pdfium

        png_dir = Path(png_dir)
        png_dir.mkdir(parents=True, exist_ok=True)
        for old in png_dir.glob(f"page-{lang}-*.png"):
            old.unlink()
        pdf = pdfium.PdfDocument(str(out_pdf))
        for i in range(len(pdf)):
            p = png_dir / f"page-{lang}-{i + 1:02d}.png"
            pdf[i].render(scale=png_ppi / 72).to_pil().save(p)
            pngs.append(p)

    if not keep_build_dir:
        shutil.rmtree(build_dir)
    return BuildResult(out_pdf, build_dir, an, list(an.warnings), pngs)
