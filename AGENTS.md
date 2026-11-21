# Instructions for coding agents

This repository turns a trip folder (`trip.yaml`, `track.gpx`, photos) into a typeset A4 PDF
report. Read `README.md` first for the architecture.

**No trip data lives in this repository.** Real trips (tracks, photos, text, reports) go in `reports/`
(or `trips/`), which are git-ignored; never move them elsewhere or commit them. `tripreport sample DEST`
generates a fictional trip (`src/tripreports/sample.py`) for trying the tool and for the tests.

## Setup and commands

```bash
make setup                      # once: .venv + editable install
.venv/bin/tripreport validate <trip-dir>
.venv/bin/tripreport build <trip-dir> --lang lt --png /tmp/pages --ppi 80
.venv/bin/tripreport clean-gpx in.gpx out.gpx    # strip heart rate etc. (always do this for a new GPX)
.venv/bin/tripreport merge-gpx d1.gpx d2.gpx out.gpx --keep <trip-dir>/gpx-days   # daily files: clean, keep, merge
make test                       # must pass before you finish (works offline)
make schema                     # after changing src/tripreports/schema.py
make sample                     # fictional sample trip in reports/sample (git-ignored) to look at
make preview TRIP=reports/<name> # build a trip and render its pages to PNG
```

Python 3.11+ from `.venv`. A build takes seconds (the first build with map tiles takes about a
minute). ReportLab renders the PDF and matplotlib draws the figures; fonts are bundled.

## Making a report for a user

1. `tripreport init reports/<name>` (or `tripreport sample`) in `reports/` and fill `trip.yaml` following
   `schema/trip.schema.json`. **Never invent facts.** Use what the user tells you; leave a field out
   rather than guess. Participants are optional.
2. GPX: run it through `clean-gpx` first (it removes heart rate, cadence and power: private data
   that must never reach the repository) and keep full point resolution (`--every 1`), because
   thinning the track shortens distance and ascent. Set `timezone` to the zone the track was recorded in.
   Daily files go through `merge-gpx --keep <trip-dir>/gpx-days` (cleaned originals kept, merged track
   written); check each file's first timestamp, file names can carry the wrong date. An expedition with
   several climbs gets one merged file per climb, listed as `gpx: [{file, name}, ...]`: each gets its own
   map and profile page.
3. Totals: GPS altitude is noisy. If the user trusts other figures (a guidebook, or a service with
   elevation correction), put them in `calibration:` (`distance_km`, `ascent_m`); every day's figures
   are scaled to match. Do not override computed numbers the user has not given.
4. Day text: use `{distance}`, `{ascent}`, `{descent}`, `{duration}`, `{hours}`, `{max_alt}`, `{min_alt}`
   for that day's figures so the diary and the tables cannot disagree. Do not end a sentence right
   after `{hours}` with a full stop (it already ends in "val.").
5. Peaks need `lat`/`lon` (copy them from the track's local maxima) so summit times are found
   automatically. Name nights through `accommodation` and long daytime stops through `breaks`;
   they label the shaded bands on the elevation profile.
6. Map: `map.basemap: tiles` puts OpenTopoMap under the route. The first build downloads the tiles and
   caches them as `basemap.jpg` + `basemap.json` in the trip folder (commit both; tests and later builds
   are then offline). Delete them to refetch. The map credit line is the only source line in the report.
7. `tripreport validate`, then `build --png <dir>`. **Look at the page PNGs** (the Read tool shows
   images) before reporting success: cover (long titles and subtitles must not collide), tables, the
   page with the map and profile (they must share one page), diary pages, photo pages, no orphaned
   headings. Warnings from `validate`/`build` (a day with no GPX points, a summit the track never comes
   near, tiles unavailable) usually mean a wrong date, timezone or coordinate: fix the cause.

## Where to change things

| Goal | Edit |
|---|---|
| New or changed field in the trip file | `schema.py`, then `document.py`, then `make schema` and the sample trip in `sample.py` |
| What a section contains, table columns, wording logic | `document.py` |
| Fixed UI wording or a new language | `assets/locales/*.toml` (keep `lt` and `en` keys identical) |
| Colours, type, spacing, radii | `assets/design/tokens.json` (the LAA design system; read `docs/design-system/`) |
| Page margins, image resolution | `assets/theme/default.toml` |
| Page layout, type sizes, title page, tables | `render.py` (renders the document model, contains no content) |
| Route map, elevation profile, optional chart | `plots.py` (plain arrays in, SVG out, returns height/width) |
| Map tiles and their cache | `basemap.py` |
| GPX statistics, rests, summit times | `gpxstats.py`, `analysis.py` (pure functions; keep them unit-tested) |

## House style (decided with the user; do not undo without asking)

- Layout follows a classic technical report: flat title page (photo above, one asphalt block below,
  nothing set over the photo, tricolour flag in its 3:5 proportions), contents on page 2 straight after
  the title page, **no summary section**, **no numbering anywhere** (sections, tables, figures),
  **no orange bars or rules above headings**, body text 10 pt justified with hyphenation, tables with a
  hairline under the header and a heavier rule at the bottom, no lines between rows, key-value tables
  without a header row.
- Colour: LAA palette. Small orange text uses `accent-text` (the darker orange), never `brand`; `brand`
  is for plot series, the track and the first title-page number. Table row names and day dates are in
  `accent-text`. Everything else is asphalt ink and greys.
- Title page: the headline numbers come from `cover_stats` (two to five; the first is accent-coloured;
  choose others for other report types). The pill under the subtitle is the report's category (`kind`,
  for example "Techninė klasė"); it is also the "Klasė" row of the general information table. There is no
  outcome line.
- Figures: the finding is the title. The route map and the elevation profile sit on one page. The map is
  all orange (no colour per day) with day-start numbers. The profile labels the nights with the hut
  names and named stops with `breaks`. No "source: GPS" lines and no captions; keep only the map-tile
  attribution. The climb-high-sleep-low chart is optional (`acclimatisation_chart: true`), off by default.
- High-altitude class ("Aukštuminė klasė") reports always set `base_camp` (altitude, arrival, departure).
  Then the daily table lists every day of the stay with a "Nakvynė" column (days without a track greyed
  out as rest days) followed by the whole-expedition altitude chart, and there is no separate table of
  nights. Give every night away from base camp an `accommodation`
  entry with its altitude, describe the camps once in `camps` (one table per mountain under
  "Nakvynės"), and add `high_point_m` to diary days that went high without a track.
- Dates are ISO, times 24 h, durations `h:mm`, gains with a sign (`+6 119 m`), thousands separated by a
  non-breaking space in Lithuanian.
- Keep the optional layout rules robust: a lone, unadorned route group has no heading row; short tables
  never split across pages or away from their heading.

## Writing report text (Lithuanian)

- The text goes into an official report: proper, natural Lithuanian in the user's voice (first-person
  plural for the team, "man" where the user speaks about themself). Informative and concrete, never stiff.
- **Never translate names.** Peaks, huts, passes, glaciers, places and routes stay in the original
  language (a peak such as Mont Blanc, a hut such as Rifugio Torino, a glacier such as Vallée Blanche). Do not decline a name by inventing a Lithuanian form.
- Use the climbers' vocabulary: katės (crampons), ledkirtis, virvė, nusileidimas virve, ketera,
  perėja, trobelė (generic "hut"), traversas (masculine: "Karališkasis traversas", not "traversa").
  If unsure of a term, ask the user.
- Reuse a participant's account only for what is common to the trip (times, places, conditions,
  hut details). Leave out what is personal to one person (their earlier summits, principles, private
  reflections). Where accounts disagree, use the more precise one and tell the user.
- Things you could not verify (for example "one of the smallest staffed huts in the Alps") are phrased
  as hedged ("manoma, kad"), and you say so in your reply. Sources found online are cited in your reply.

## Code rules

- All reader-facing text goes through `Locale` and `resolve()`: no hard-coded Lithuanian or English in
  `document.py` or `render.py`. Numbers and dates are formatted in Python, not in the renderer.
- User text reaches ReportLab only through `markup()` / `runs_markup()` (XML-escaped), so it cannot break
  the paragraph parser.
- Keep `plots.py` and `gpxstats.py` free of file-system and global state beyond their arguments; a server
  will call them.
- The tests are the regression suite; they build a generated sample trip and need no network. After
  any change that affects output, build a trip (the sample or a real one in `reports/`), look at the
  pages, and run `make test`.
- `docs/design-system/` is a verbatim copy of the design system's documents; do not edit it.

## Privacy and housekeeping

- Never commit generated output (`out/`, `.build-*`), raw GPX files with sensor data, or real people's
  contact details. The sample trip is fictional and its pictures are drawn, not photographed.
- Do not name the brands that inspired the look in code, docs, commit messages or reports. The palette
  and layout are described on their own terms.
- Commit and push only when the user asks. Work happens on the `feat/scaffold-trip-reports` branch
  with draft PR #1.
