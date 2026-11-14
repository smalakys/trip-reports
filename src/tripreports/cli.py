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
                           theme_path=args.theme, template=args.template,
                           png_dir=args.png, png_ppi=args.ppi)
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
summary: []
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
    b.add_argument("--template", help="custom Typst template instead of the built-in one")
    b.add_argument("--png", metavar="DIR", help="also render every page to PNG in DIR (for previewing)")
    b.add_argument("--ppi", type=int, default=70, help="resolution of the PNG previews")
    b.set_defaults(fn=_cmd_build)

    v = sub.add_parser("validate", help="check a trip folder without building")
    v.add_argument("trip")
    v.set_defaults(fn=_cmd_validate)

    s = sub.add_parser("schema", help="print the JSON Schema of trip.yaml")
    s.add_argument("--out", help="write to a file instead of stdout")
    s.set_defaults(fn=_cmd_schema)

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
