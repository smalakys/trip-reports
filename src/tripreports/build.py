"""The build pipeline: trip folder -> prepared assets -> figures -> data bundle -> Typst -> PDF."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import typst

from . import plots
from .analysis import Analysis, acclimatisation_points, analyse
from .document import Assets, build_document
from .i18n import Locale
from .images import prepare_image
from .schema import Trip, load_trip
from .theme import FONTS_DIR, TEMPLATES_DIR, load_theme


@dataclass
class BuildResult:
    pdf: Path
    build_dir: Path
    analysis: Analysis
    warnings: list[str] = field(default_factory=list)
    pngs: list[Path] = field(default_factory=list)


def _check_files(trip: Trip, trip_dir: Path) -> None:
    missing = [p for p in [trip.gpx, trip.cover.image, *(ph.file for ph in trip.photos)]
               if not (trip_dir / p).exists()]
    if missing:
        raise FileNotFoundError("files listed in the trip file are missing: " + ", ".join(missing))


def build_report(
    trip_dir: str | Path,
    lang: str | None = None,
    out: str | Path | None = None,
    theme_path: str | Path | None = None,
    template: str | Path | None = None,
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
    map_ratio = plots.route_map(an.track, an.day_start_idx, an.peaks, theme, loc,
                                assets_dir / "route-map.svg", basemap=trip.map.basemap,
                                color_by=trip.map.color_by, label_peaks=trip.map.label_peaks)
    prof_ratio = plots.elevation_profile(an.track, an.rest_spans, an.peaks, theme, loc,
                                         assets_dir / "elevation-profile.svg")

    acc_file, acc_ratio, acc_delta = None, 0.0, 0.0
    if len(an.days) >= 3:
        points, summit = acclimatisation_points(an, lambda n: f"{loc.ui('day')} {n}")
        gaps = [p.high_m - p.sleep_m for p in points if p.sleep_m is not None]
        acc_file, acc_delta = "assets/climb-high-sleep-low.svg", float(sum(gaps) / len(gaps))
        acc_ratio = plots.acclimatisation_chart(points, summit, theme, loc, assets_dir / "climb-high-sleep-low.svg")

    assets = Assets(cover="assets/cover.jpg", cover_px=cover_px,
                    route_map="assets/route-map.svg", route_map_ratio=map_ratio,
                    profile="assets/elevation-profile.svg", profile_ratio=prof_ratio,
                    acc=acc_file, acc_ratio=acc_ratio, acc_delta_m=acc_delta, photos=photos)
    doc = build_document(trip, an, assets, theme, lang)
    (build_dir / "data.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copy(Path(template) if template else TEMPLATES_DIR / "report.typ", build_dir / "report.typ")

    common = dict(root=str(build_dir), font_paths=[str(FONTS_DIR)], ignore_system_fonts=True)
    typst.compile(str(build_dir / "report.typ"), output=str(out_pdf), **common)

    pngs: list[Path] = []
    if png_dir:
        png_dir = Path(png_dir)
        png_dir.mkdir(parents=True, exist_ok=True)
        for old in png_dir.glob(f"page-{lang}-*.png"):
            old.unlink()
        pages = typst.compile(str(build_dir / "report.typ"), format="png", ppi=png_ppi, **common)
        pages = pages if isinstance(pages, list) else [pages]
        for i, data in enumerate(pages, start=1):
            p = png_dir / f"page-{lang}-{i:02d}.png"
            p.write_bytes(data)
            pngs.append(p)

    if not keep_build_dir:
        shutil.rmtree(build_dir)
    return BuildResult(out_pdf, build_dir, an, list(an.warnings), pngs)
