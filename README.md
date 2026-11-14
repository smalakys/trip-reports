# trip-reports

Publication-ready mountaineering trip reports from a trip file, a GPX track and photos.

```
trips/my-climb/
  trip.yaml     <- the report's content (validated against schema/trip.schema.json)
  track.gpx     <- recorded track: used for the map, elevation profile, day statistics, summit times
  photos/       <- cover and report photos
```

`tripreport build trips/my-climb --lang lt` produces a typeset A4 PDF: cover, summary, contents,
general information, route tables, per-day statistics, diary, route map, elevation profile and
photo pages. Content can be written in several languages (Lithuanian and English are built in).

## Quick start

```bash
make setup      # creates .venv and installs the package (Python 3.11+)
make example    # builds the synthetic example in Lithuanian and English
make test       # unit tests + a full build of the example
```

Open `examples/synthetic-traverse/out/report-lt.pdf` (or `-en`). The example uses fictional data
and is the reference for how a report should look and for what a correct build produces: if you
change code, templates or the theme, rebuild it and compare with
[`examples/synthetic-traverse/preview/`](examples/synthetic-traverse/preview).

```bash
tripreport init trips/my-climb                      # new trip folder with a starter trip.yaml
tripreport validate trips/my-climb                  # check the file, referenced files and the track
tripreport build trips/my-climb --lang lt --lang en # PDFs in trips/my-climb/out/
tripreport build trips/my-climb --png /tmp/pages    # also render every page to PNG for a quick look
tripreport schema                                   # JSON Schema of trip.yaml
```

## How it works

```
trip.yaml ──┐
track.gpx ──┼─> analysis.py ──> document.py ──> data.json ──┐
photos/ ────┘    (stats, summits)  (language-specific       ├─> Typst ──> report.pdf
                  plots.py          blocks: headings,       │   (templates/report.typ)
                  (SVG figures)     tables, figures, ...)  ─┘
```

| Layer | File | Purpose |
|---|---|---|
| Schema | `src/tripreports/schema.py` | The contract. Pydantic models; JSON Schema is generated from them. |
| Analysis | `gpxstats.py`, `analysis.py` | Distance, ascent/descent (noise-filtered), per-day stats, rests, summit times. |
| Figures | `plots.py` | Route map and elevation profile as SVG (matplotlib). Plain inputs, no global state. |
| Document model | `document.py` | Decides what appears: sections, tables, wording, number and date formats per language. |
| Layout | `assets/templates/report.typ` | Typst template; only renders the document model. |
| Look | `assets/theme/default.toml` | Colours, font, page geometry, text sizes, image resolution. |
| Wording | `assets/locales/*.toml` | UI strings, months, number formats. |

Because the content lives in `trip.yaml` and the output is a pure function of the trip folder, the
same `build_report()` can sit behind a CLI, an agent, or later a web or mobile front end (the JSON
Schema can drive its forms).

## Writing `trip.yaml`

See the commented [example](examples/synthetic-traverse/trip.yaml) and `schema/trip.schema.json`.
Points worth knowing:

- **Localised text** is either a plain string or `{lt: "...", en: "..."}`. `languages:` lists the
  languages the file is written in; the first is the default for `tripreport build`.
- **Summits:** give `lat`/`lon` and the summit time and date are found in the GPX track
  automatically. Or give `date` and `time` yourself.
- **Days:** diary entries (`days:`) also define which dates get a row in the daily table.
  `day_cutoff_hour: 3` makes a "day" run 03:00 to 03:00 (useful for alpine starts after midnight).
- **Rests:** nights and stops of 2.5 h or more are detected from the track and shaded in the
  profile; the daily duration excludes them.
- **Text markup:** blank line = paragraph; `**bold**`, `*italic*`.
- **Photos:** `size: full` puts a photo on a page of its own; `half` places two per page.
- **Map:** `map.basemap: plain` works offline; `tiles` downloads light map tiles
  (`pip install -e ".[tiles]"`, needs network) and adds the attribution line.

## Changing the look

- Colours, font, page margins, text sizes: copy `src/tripreports/assets/theme/default.toml`,
  edit it, and pass `--theme my-theme.toml`. Fonts are bundled (Inter, SIL OFL); the build ignores
  system fonts so output is identical on every machine.
- Layout: copy `src/tripreports/assets/templates/report.typ` and pass `--template my.typ`.
- New language: add `assets/locales/<code>.toml` (copy `en.toml`).

## Layout of the repository

```
src/tripreports/      the package (see table above)
schema/               generated JSON Schema (keep current with `make schema`)
examples/             synthetic-traverse: fictional trip; generate.py rebuilds its GPX and photos
tests/                unit tests and an end-to-end build of the example
AGENTS.md             instructions for coding agents
```

## Roadmap

A web form and an iOS app for non-technical users (enter details, upload photos, export PDF) are
planned. They would send a trip folder to a small server that calls `build_report()`; no
rendering logic lives outside this package.
