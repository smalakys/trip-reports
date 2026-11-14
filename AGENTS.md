# Instructions for coding agents

This repository turns a trip folder (`trip.yaml`, `track.gpx`, photos) into a typeset PDF.
Read `README.md` first for the architecture.

## Setup and commands

```bash
make setup                      # once: .venv + editable install
.venv/bin/tripreport validate <trip-dir>
.venv/bin/tripreport build <trip-dir> --lang lt --png /tmp/pages --ppi 80
make test                       # must pass before you finish
make schema                     # after changing src/tripreports/schema.py
make data                       # only if you change examples/synthetic-traverse/generate.py
```

Use Python 3.11+ from `.venv`. A build takes a few seconds; there is no other toolchain
(Typst is installed as a Python package, fonts are bundled).

## Making a report for a user

1. `tripreport init trips/<name>` (or copy the example) and fill `trip.yaml` following
   `schema/trip.schema.json`. Never invent facts: leave a field out instead.
2. Put the GPX at `track.gpx` and photos under `photos/`. Set `timezone` to the IANA zone of
   the place the track was recorded.
3. `tripreport validate`, then `build --png <dir>`. **Look at the page PNGs** (the Read tool
   shows images) before reporting success: check the cover, tables, both figures and photo pages.
4. Warnings from `validate`/`build` (e.g. "no GPX points on <date>", a summit the track never
   comes near) usually mean a wrong date, timezone, or coordinate: fix the cause.

## Where to change things

| Goal | Edit |
|---|---|
| New or changed field in the trip file | `schema.py`, then `document.py`, then `make schema` and update the example |
| What a section contains, table columns, wording logic | `document.py` |
| Fixed UI wording or a new language | `assets/locales/*.toml` (keep `lt` and `en` keys identical) |
| Colours, fonts, margins, sizes | `assets/theme/default.toml` |
| Page layout and typography | `assets/templates/report.typ` (renders `data.json`, contains no content) |
| Route map or elevation profile | `plots.py` (inputs are plain arrays; returns height/width ratio) |
| GPX statistics | `gpxstats.py` (pure functions; keep them unit-tested) |

## Rules

- The synthetic example is the reference. After any change that affects output, rebuild it,
  look at the pages, and update `examples/synthetic-traverse/preview/` (`make update-preview`)
  only if the change is intended.
- All reader-facing text goes through `Locale` and `resolve()`: no hard-coded Lithuanian or
  English in `document.py` or the template. Numbers and dates are formatted in Python, not Typst.
- User text is passed to Typst as data (JSON), never spliced into Typst source, so it cannot
  break or inject markup.
- Keep `plots.py` and `gpxstats.py` free of file-system and global state beyond their arguments;
  a server will call them.
- Do not commit generated output (`out/`, `.build-*`) or real trips' private data.
