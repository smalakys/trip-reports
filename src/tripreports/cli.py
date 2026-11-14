"""Command line interface: ``tripreport build|validate|schema|init``."""

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
                           png_dir=args.png, png_ppi=args.ppi, mode=args.mode)
        for w in res.warnings:
            print(f"warning: {w}", file=sys.stderr)
        print(f"wrote {res.pdf}" + (f" and {len(res.pngs)} page images in {args.png}" if args.png else ""))
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


def _cmd_clean_gpx(args) -> int:
    """Rewrite a GPX with only position, altitude and time (no heart rate, cadence or power)."""
    import gpxpy
    import gpxpy.gpx

    with open(args.src, encoding="utf-8") as fh:
        src = gpxpy.parse(fh)
    out = gpxpy.gpx.GPX()
    out.creator = "tripreports clean-gpx"
    for trk in src.tracks:
        t = gpxpy.gpx.GPXTrack(name=trk.name)
        for seg in trk.segments:
            ns = gpxpy.gpx.GPXTrackSegment()
            last = len(seg.points) - 1
            for i, p in enumerate(seg.points):
                if i % args.every == 0 or i == last:
                    ns.points.append(gpxpy.gpx.GPXTrackPoint(
                        round(p.latitude, 6), round(p.longitude, 6),
                        elevation=None if p.elevation is None else round(p.elevation, 1), time=p.time))
            t.segments.append(ns)
        out.tracks.append(t)
    Path(args.dest).write_text(out.to_xml(), encoding="utf-8")
    n = sum(len(s.points) for t in out.tracks for s in t.segments)
    print(f"wrote {args.dest}: {n} points (kept every {args.every}th; removed sensor data)")
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
    b.set_defaults(fn=_cmd_build)

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
