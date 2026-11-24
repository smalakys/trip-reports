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
    web_pdf: Path | None = None
    web_error: str | None = None  # why no web copy was written (e.g. Ghostscript missing)


def _check_files(trip: Trip, trip_dir: Path) -> None:
    missing = [p for p in [*(f.file for f in trip.gpx_files()), trip.cover.image, *(ph.file for ph in trip.photos),
                                                                 *(tp.file for tp in trip.route_topos)]
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
    web: bool = True,
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

    topos = []
    for i, tp in enumerate(trip.route_topos, start=1):
        name = f"topo-{i:02d}.jpg"
        px = prepare_image(trip_dir / tp.file, assets_dir / name, img["photo_long_edge_px"], img["jpeg_quality"])
        topos.append((f"assets/{name}", px))

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
    def tiles_for(view, name: str, max_zoom: int):
        """The tile image cropped to ``view``, from a cache of its own (None: draw the plain map)."""
        if trip.map.basemap != "tiles":
            return None
        try:
            from .basemap import crop_and_tone, load_basemap

            x0, x1, y0, y1 = view.extent
            w, h = x1 - x0, y1 - y0
            bm = load_basemap(trip_dir, (x0 - 0.05 * w, x1 + 0.05 * w, y0 - 0.05 * h, y1 + 0.05 * h),
                              trip.map.tile_source, name=name, max_zoom=max_zoom)
            return crop_and_tone(bm, view.extent, desaturate=0.55, lighten=0.1)
        except Exception as exc:
            an.warnings.append(f"map tiles unavailable for {name} ({exc}); drew the plain map instead")
            return None

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

    # the optional zoomed-in map: the first figure's track over a smaller window, with sharper tiles of its own
    if trip.map.detail is not None:
        d = trip.map.detail
        track, day_starts, _, peaks, _ = views[0]
        view = plots.detail_view(track, d.above_m, d.bounds)
        base_image = tiles_for(view, "basemap-detail", 17)
        ratio = plots.route_map(track, day_starts, peaks, theme, loc, assets_dir / "route-map-detail.svg",
                                color_by=trip.map.color_by, label_peaks=trip.map.label_peaks,
                                base_image=base_image, base_out=assets_dir / "route-map-detail-base.jpg", view=view)
        figures[0].detail, figures[0].detail_ratio = "assets/route-map-detail.svg", ratio
        figures[0].detail_under = "assets/route-map-detail-base.jpg" if base_image is not None else None

    # the optional overview: every GPX file together, its tiles cached apart from the per-file map's
    overview = None
    if trip.map.overview is not None:
        if not an.groups:
            an.warnings.append("map.overview needs several GPX files with figures; left out")
        else:
            view = plots.map_view(an.track)
            base_image = tiles_for(view, "basemap-overview", 16)
            ratio = plots.route_map(an.track, an.day_start_idx, an.peaks, theme, loc,
                                    assets_dir / "route-map-overview.svg", color_by=trip.map.color_by,
                                    label_peaks=trip.map.label_peaks, base_image=base_image,
                                    base_out=assets_dir / "route-map-overview-base.jpg", view=view)
            prof = plots.elevation_profile(an.track, an.rest_spans, an.peaks, theme, loc,
                                           assets_dir / "elevation-profile-overview.svg",
                                           rest_labels=label_rests(trip, an.rest_spans), height_ratio=0.35)
            overview = GroupFigures(
                route_map="assets/route-map-overview.svg", route_map_ratio=ratio,
                route_map_under="assets/route-map-overview-base.jpg" if base_image is not None else None,
                profile="assets/elevation-profile-overview.svg", profile_ratio=prof)

    alt_file, alt_ratio = None, 0.0
    if an.expedition:
        index = {d.date: i for i, d in enumerate(an.expedition)}
        summits = [(p.name, p.elevation_m, index[p.time.date()]) for p in an.peaks
                   if p.time is not None and p.time.date() in index]
        alt_file = "assets/altitude-chart.svg"
        alt_ratio = plots.altitude_chart(an.expedition, summits, trip.base_camp.altitude_m, theme, loc,
                                         assets_dir / "altitude-chart.svg")

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
                    detail=first.detail, detail_ratio=first.detail_ratio, detail_under=first.detail_under,
                    acc=acc_file, acc_ratio=acc_ratio, acc_delta_m=acc_delta, photos=photos, topos=topos,
                    groups=figures if an.groups else [], overview=overview, alt_chart=alt_file, alt_chart_ratio=alt_ratio)
    doc = build_document(trip, an, assets, theme, lang)
    (build_dir / "data.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    render_pdf(doc, out_pdf, build_dir)

    web_pdf: Path | None = None
    web_error = None
    if web:
        from .compress import compress_pdf

        try:
            web_pdf = compress_pdf(out_pdf)
        except RuntimeError as e:
            web_error = str(e)

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
    return BuildResult(out_pdf, build_dir, an, list(an.warnings), pngs, web_pdf, web_error)
