"""Command line interface: ``tripreport build|validate|schema|clean-gpx|merge-gpx|sample|init``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import SCHEMA_VERSION


def _cmd_build(args) -> int:
    from .build import build_report

    langs = args.lang or [None]
    for lang in langs:
        res = build_report(args.trip, lang=lang, out=args.out if len(langs) == 1 else None,
                           theme_path=args.theme,
                           png_dir=args.png, png_ppi=args.ppi, mode=args.mode, web=not args.no_web)
        for w in res.warnings:
            print(f"warning: {w}", file=sys.stderr)
        if res.web_pdf:
            print(f"wrote {res.web_pdf} ({res.web_pdf.stat().st_size / 1e6:.1f} MB, for email and the web)")
        if res.web_error:
            print(f"warning: no web copy written: {res.web_error}", file=sys.stderr)
        print(f"wrote {res.pdf}" + (f" and {len(res.pngs)} page images in {args.png}" if args.png else ""))
    return 0


def _cmd_compress(args) -> int:
    from .compress import compress_pdf

    out = compress_pdf(args.src, args.dst, ppi=args.ppi, quality=args.quality)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


def _cmd_validate(args) -> int:
    from .analysis import analyse
    from .build import _check_files
    from .schema import load_trip

    trip, trip_dir = load_trip(args.trip)
    _check_files(trip, trip_dir)
    an = analyse(trip, trip_dir)
    for w in an.warnings:
        print(f"warning: {w}", file=sys.stderr)
    print(f"ok: {trip_dir} ({len(trip.days)} diary days, {len(trip.photos)} photos, "
          f"{len(an.track)} track points)")
    return 0


def _cmd_schema(args) -> int:
    from .schema import json_schema

    text = json.dumps(json_schema(), indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def _clean_tracks(src: Path, every: int) -> list:
    """The tracks of one GPX file with only position, altitude and time (every Nth point kept)."""
    import gpxpy
    import gpxpy.gpx

    with open(src, encoding="utf-8") as fh:
        gpx = gpxpy.parse(fh)
    tracks = []
    for trk in gpx.tracks:
        t = gpxpy.gpx.GPXTrack(name=trk.name)
        for seg in trk.segments:
            ns = gpxpy.gpx.GPXTrackSegment()
            last = len(seg.points) - 1
            for i, p in enumerate(seg.points):
                if i % every == 0 or i == last:
                    ns.points.append(gpxpy.gpx.GPXTrackPoint(
                        round(p.latitude, 6), round(p.longitude, 6),
                        elevation=None if p.elevation is None else round(p.elevation, 1), time=p.time))
            t.segments.append(ns)
        tracks.append(t)
    return tracks


def _write_gpx(tracks: list, dest: str | Path, note: str) -> None:
    import gpxpy.gpx

    out = gpxpy.gpx.GPX()
    out.creator = "tripreports clean-gpx"
    out.tracks = tracks
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(out.to_xml(), encoding="utf-8")
    n = sum(len(s.points) for t in tracks for s in t.segments)
    print(f"wrote {dest}: {n} points ({note}; removed sensor data)")


def _cmd_clean_gpx(args) -> int:
    """Rewrite a GPX with only position, altitude and time (no heart rate, cadence or power)."""
    _write_gpx(_clean_tracks(Path(args.src), args.every), args.dest, f"kept every {args.every}th")
    return 0


def _first_time(track):
    times = [p.time for s in track.segments for p in s.points if p.time is not None]
    return min(times) if times else None


def _cmd_merge_gpx(args) -> int:
    """Clean several GPX files (one per day, say) and join them into one track file in time order.

    With ``--keep DIR`` the cleaned single files are written there too, under their own names, so
    the trip folder keeps the daily originals (without sensor data) next to the merged track.
    """
    import datetime as dt

    tracks = []
    for src in map(Path, args.src):
        cleaned = _clean_tracks(src, args.every)
        if args.keep:
            _write_gpx(cleaned, Path(args.keep) / src.name, "kept original")
        tracks += cleaned
    far = dt.datetime.max.replace(tzinfo=dt.UTC)
    tracks.sort(key=lambda t: _first_time(t) or far)
    _write_gpx(tracks, args.dest, f"{len(args.src)} files merged in time order")
    return 0


def _cmd_sample(args) -> int:
    from .sample import create_sample

    dest = Path(args.dest)
    if dest.exists() and any(dest.iterdir()):
        print(f"error: {dest} is not empty", file=sys.stderr)
        return 1
    create_sample(dest)
    print(f"wrote a fictional sample trip to {dest}; try: tripreport build {dest} --lang lt")
    return 0


_INIT_TRIP = """\
# yaml-language-server: $schema=../../schema/trip.schema.json
schema_version: {schema}
languages: [lt]
title: {title}
subtitle: ""
cover: {{image: photos/cover.jpg, kicker: "Įkopimo ataskaita"}}
start_date: 2025-01-01
end_date: 2025-01-02
timezone: Europe/Zurich
region: ""
participants:
  - name: Your Name
gpx: track.gpx
days: []
photos: []
"""


def _cmd_init(args) -> int:
    dest = Path(args.dest)
    if dest.exists() and any(dest.iterdir()):
        print(f"error: {dest} is not empty", file=sys.stderr)
        return 1
    (dest / "photos").mkdir(parents=True, exist_ok=True)
    (dest / "trip.yaml").write_text(_INIT_TRIP.format(schema=SCHEMA_VERSION, title=dest.name), encoding="utf-8")
    print(f"created {dest}/trip.yaml - add track.gpx and photos/cover.jpg, then run: tripreport build {dest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tripreport", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build a PDF from a trip folder")
    b.add_argument("trip", help="trip folder containing trip.yaml")
    b.add_argument("--lang", action="append", help="language code; repeat for several (default: first in trip file)")
    b.add_argument("--out", help="output PDF (single language only); default <trip>/out/report-<lang>.pdf")
    b.add_argument("--theme", help="theme TOML overriding the defaults")
    b.add_argument("--mode", choices=["light", "dark"], help="colour mode (default: from the theme, light)")
    b.add_argument("--png", metavar="DIR", help="also render every page to PNG in DIR (for previewing)")
    b.add_argument("--ppi", type=int, default=70, help="resolution of the PNG previews")
    b.add_argument("--no-web", action="store_true",
                   help="skip the smaller report-<lang>-web.pdf copy for email and the web (needs Ghostscript)")
    b.set_defaults(fn=_cmd_build)

    z = sub.add_parser("compress", help="write a smaller copy of a PDF for email and the web (Ghostscript)")
    z.add_argument("src")
    z.add_argument("dst", nargs="?", help="default: <src>-web.pdf")
    z.add_argument("--ppi", type=int, default=200, help="resolution photographs are downsampled to")
    z.add_argument("--quality", type=float, default=0.4, help="JPEG QFactor: lower is better")
    z.set_defaults(fn=_cmd_compress)

    v = sub.add_parser("validate", help="check a trip folder without building")
    v.add_argument("trip")
    v.set_defaults(fn=_cmd_validate)

    s = sub.add_parser("schema", help="print the JSON Schema of trip.yaml")
    s.add_argument("--out", help="write to a file instead of stdout")
    s.set_defaults(fn=_cmd_schema)

    g = sub.add_parser("clean-gpx", help="strip heart rate etc. from a GPX and thin out its points")
    g.add_argument("src")
    g.add_argument("dest")
    g.add_argument("--every", type=int, default=3, help="keep every Nth point (default 3)")
    g.set_defaults(fn=_cmd_clean_gpx)

    mg = sub.add_parser("merge-gpx", help="clean several GPX files (e.g. one per day) and join them in time order")
    mg.add_argument("src", nargs="+", help="input GPX files")
    mg.add_argument("dest", help="merged GPX to write")
    mg.add_argument("--every", type=int, default=1, help="keep every Nth point (default 1: all)")
    mg.add_argument("--keep", metavar="DIR", help="also write each cleaned input file to DIR")
    mg.set_defaults(fn=_cmd_merge_gpx)

    sm = sub.add_parser("sample", help="write a small fictional sample trip to try the tool")
    sm.add_argument("dest")
    sm.set_defaults(fn=_cmd_sample)

    i = sub.add_parser("init", help="create a new trip folder")
    i.add_argument("dest")
    i.set_defaults(fn=_cmd_init)

    ap.add_argument("--debug", action="store_true", help="show tracebacks")
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except Exception as exc:  # user-facing errors: short message, no traceback
        if args.debug:
            raise
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
