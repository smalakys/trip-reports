# trip-reports

Publication-ready mountaineering trip reports from a trip file, a GPX track and photos.

```
reports/my-climb/
  trip.yaml     <- the report's content (validated against schema/trip.schema.json)
  track.gpx     <- recorded track: used for the map, elevation profile, day statistics, summit times
  photos/       <- cover and report photos
```

`tripreport build reports/my-climb --lang lt` produces a typeset A4 PDF: cover, contents,
general information, route tables, per-day statistics, diary, route map, elevation profile,
route map with a real basemap, elevation profile and photo pages. Content can be written in several languages (Lithuanian and English are built in).

## Quick start

```bash
make setup      # creates .venv and installs the package (Python 3.11+)
make sample     # writes a fictional sample trip to reports/sample (git-ignored)
make build      # builds reports/sample/out/report-lt.pdf
make test       # unit tests and end-to-end builds of a generated sample trip (no network needed)
```

The repository ships no trip data. Your own trips live in `reports/` (or `trips/`), both git-ignored,
so real tracks, photos and reports are never committed. `tripreport sample DEST` writes a small
fictional trip (invented people, peaks and track, drawn pictures) that shows what a complete trip
folder looks like and what the report looks like; the tests build the same trip.

```bash
tripreport sample reports/sample                    # a fictional trip to try the tool on
tripreport init reports/my-climb                    # new trip folder with a starter trip.yaml
tripreport clean-gpx in.gpx reports/my-climb/track.gpx --every 1   # keep position, altitude, time only
tripreport validate reports/my-climb                # check the file, referenced files and the track
tripreport build reports/my-climb --lang lt         # PDF in reports/my-climb/out/
tripreport build reports/my-climb --png /tmp/pages  # also render every page to PNG for a quick look
tripreport schema                                   # JSON Schema of trip.yaml
```

## How it works

```
trip.yaml ──┐
track.gpx ──┼─> analysis.py ──> document.py ──> data.json ──┐
photos/ ────┘    (stats, summits)  (language-specific       ├─> ReportLab ──> report.pdf
                  plots.py          blocks: headings,       │   (render.py)
                  (SVG figures)     tables, figures, ...)  ─┘
```

| Layer | File | Purpose |
|---|---|---|
| Schema | `src/tripreports/schema.py` | The contract. Pydantic models; JSON Schema is generated from them. |
| Analysis | `gpxstats.py`, `analysis.py` | Distance, ascent/descent (noise-filtered), per-day stats, rests, summit times. |
| Figures | `plots.py` | Route map and elevation profile as SVG (matplotlib). Plain inputs, no global state. |
| Document model | `document.py` | Decides what appears: sections, tables, wording, number and date formats per language. |
| Layout | `render.py` | ReportLab renderer: page grid, headings, tables, figures, title page, contents and PDF bookmarks. Only renders the document model. |
| Look | `assets/design/tokens.json`, `assets/theme/default.toml` | The LAA design tokens (colour in light and dark, type, spacing, radii) plus page geometry and image resolution. See `docs/design-system/`. |
| Wording | `assets/locales/*.toml` | UI strings, months, number formats. |

Because the content lives in `trip.yaml` and the output is a pure function of the trip folder, the
same `build_report()` can sit behind a CLI, an agent, or later a web or mobile front end (the JSON
Schema can drive its forms).

## Writing `trip.yaml`

See the sample trip file (`tripreport sample`, the text is in `src/tripreports/sample.py`) and `schema/trip.schema.json`.
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
- **Title-page numbers:** `cover_stats` picks the headline numbers (two to five, the first in the accent colour) from `highest_point`, `ascent`, `descent`, `distance`, `peaks`, `days`, `net_time`, `vertical_range`. The default suits a multi-day climb; choose others for other kinds of report.
- **Profile labels:** nights on the elevation profile are named after the `accommodation` entry for that date; `breaks:` names a long daytime stop (`{date, place}`, e.g. a hut). The optional climb-high-sleep-low chart is switched on with `acclimatisation_chart: true`.
- **Calibration:** GPS altitude is noisy, so computed ascent is rarely exact. `calibration:` (`distance_km`, `ascent_m`, optional `descent_m`) sets the totals you trust; every day's figures are scaled by the same factor so tables still add up. Day texts can use `{distance}`, `{ascent}`, `{descent}`, `{duration}`, `{hours}`, `{max_alt}`, `{min_alt}` to quote that day's figures.
- **Grades:** give a route group `grade` (as the guidebook writes it) and `grade_system` (Alpine, UIAA, Cat.); they become badges.
- **Dates and numbers:** dates are ISO, times 24 h, durations `h:mm`, in every language.
- **Photos:** `size: full` puts a photo on a page of its own; `half` places two per page.
- **Map:** `map.basemap: plain` draws a flat grid and works offline. `tiles` puts a real map under the
  route (`tile_source: topo` = OpenTopoMap with contours and glaciers, `light` = a minimal grey map; needs
  `pip install -e ".[tiles]"`). Tiles are downloaded on the first build and cached as `basemap.jpg` and
  `basemap.json` in the trip folder, so later builds are offline; delete them to refetch. The attribution
  line is added automatically.
- **GPX files:** `tripreport clean-gpx in.gpx out.gpx` keeps only position, altitude and time, so heart
  rate and other sensor data never reach the repository.

## Changing the look

The look is the LAA design system: Barlow type, one orange, asphalt and chalk neutrals, flat and
sharp. [`docs/design-system/`](docs/design-system/README.md) maps each part of the system to the code.

- Colours, type, spacing, radii: `src/tripreports/assets/design/tokens.json`. All figures and the
  renderer read the resolved tokens, so a changed token changes the whole report.
- Page margins, image resolution, colour overrides for one trip: copy
  `src/tripreports/assets/theme/default.toml`, edit it, pass `--theme my-theme.toml`.
- Dark variant: `tripreport build <trip> --mode dark`.
- Fonts are bundled (Barlow family, SIL OFL); the build ignores system fonts so output is identical
  on every machine.
- Layout: page grid, type sizes and table rules are in `src/tripreports/render.py` (`make_styles`, `Report`).
- New language: add `assets/locales/<code>.toml` (copy `en.toml`).

## Layout of the repository

```
src/tripreports/      the package (see table above)
schema/               generated JSON Schema (keep current with `make schema`)
reports/              your trips and their PDFs (git-ignored, never committed)
tests/                unit tests and end-to-end builds of a generated sample trip
AGENTS.md             instructions for coding agents
```

## Roadmap

A web form and an iOS app for non-technical users (enter details, upload photos, export PDF) are
planned. They would send a trip folder to a small server that calls `build_report()`; no
rendering logic lives outside this package.
