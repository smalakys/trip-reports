# LAA design system in this repository

The reports follow the Lithuanian Mountaineering Association (LAA) design system. The files in
this folder are its brand book, plot rules and component guidelines; the code implements them.

| Design system | Where it lives in the code |
|---|---|
| Tokens (colour light/dark, type, spacing, radius) | `src/tripreports/assets/design/tokens.json`, resolved by `theme.py` (`load_theme(mode=...)`) |
| Barlow, Barlow Condensed, Barlow Semi Condensed | `src/tripreports/assets/fonts/` (OFL), used by Typst and matplotlib |
| Page, image and plot settings | `src/tripreports/assets/theme/default.toml` (+ `--theme` overrides) |
| **ReportHeader** (title page) | `report.typ`, title-page block; data in `document.py` (`cover`). Photo above, one asphalt block below, tricolour strip, grade badges, outcome |
| **StatGroup** | `stat-group()` in `report.typ`; five headline numbers on the title page, the highest point in the accent colour |
| **GradeBadge** | `grade-badge()` in `report.typ`; `grade` / `grade_system` in `trip.yaml` |
| **ElevationProfile** | `plots.elevation_profile()`; time on x so nights show as `surface-200` bands, summits flagged with `peak` weight heights |
| **AcclimatisationChart** | `plots.acclimatisation_chart()`; built from the GPX when a trip has three or more days |
| Route map (not in the design system) | `plots.route_map()`, flat map in `surface-100`, track in `series-1`, day colours `series-1..5` |
| Tables (header rows `surface-200`, hairline rows, `label` headers) | `render-table()` in `report.typ` |
| **Button** | Web and app only; nothing in a PDF |
| Dates ISO, times 24 h, durations `h:mm`, `+2 140 m` gains, thin-space thousands | `i18n.py` |

Notes on choices the design system leaves open for print:

- The title page keeps a full-bleed photo (trip reports are not technical documents) but nothing is
  set over it: the report header sits in its own asphalt block below, as the system asks.
- Type sizes are the token pixel sizes converted to points (1 px = 0.75 pt), so body text is 12 pt.
- Orange text uses `accent-text` (never `brand`) and appears on table row names and day dates;
  `brand` is for fills, plot series and the one accent stat.
- Dark mode (`tripreport build --mode dark`) swaps every token for its dark value. The
  `surface-inverse` title block follows the tokens and so turns light in dark mode.

`brand-book.md`, `plots.md` and `components/` are the design system's own documents, kept here for
reference. Change the system in its source and copy the files again; do not edit them here.
