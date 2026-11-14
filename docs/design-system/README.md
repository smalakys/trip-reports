# LAA design system in this repository

The reports use the Lithuanian Mountaineering Association (LAA) palette, type and chart rules on a
classic technical-report layout. The files in this folder are the design system's own brand book,
plot rules and component guidelines; the code implements them.

| Design system | Where it lives in the code |
|---|---|
| Tokens (colour light/dark, type, spacing, radius) | `src/tripreports/assets/design/tokens.json`, resolved by `theme.py` (`load_theme(mode=...)`) |
| Barlow, Barlow Condensed, Barlow Semi Condensed | `src/tripreports/assets/fonts/` (OFL), used by `render.py` (ReportLab) and `plots.py` (matplotlib) |
| Page and image settings | `src/tripreports/assets/theme/default.toml` (+ `--theme` overrides) |
| **ReportHeader** (title page) | `Report._cover_page()` in `render.py`; data in `document.py` (`cover`). Photo above, one asphalt block below, tricolour strip, grade badges, outcome |
| **StatGroup** | `Report._cover_stats()`; five headline numbers on the title page, the highest point in the accent colour |
| **GradeBadge** | `GradeBadge` flowable in `render.py`; `grade` / `grade_system` in `trip.yaml` |
| **ElevationProfile** | `plots.elevation_profile()`; time on x so nights show as `surface-200` bands, summits flagged with `peak` weight heights |
| **AcclimatisationChart** | `plots.acclimatisation_chart()`; built from the GPX when `acclimatisation_chart: true` and the trip has three or more days |
| Route map (not in the design system) | `plots.route_map()`, flat map in `surface-100`, track in `series-1`, day colours `series-1..5` |
| Tables | `Report.table()`: hairline under the header, a heavier rule at the bottom, no lines between rows |
| **Button** | Web and app only; nothing in a PDF |
| Dates ISO, times 24 h, durations `h:mm`, `+2 140 m` gains, thin-space thousands | `i18n.py` |

Notes on choices the design system leaves open for print:

- Page grid: A4, 20 mm left and 15 mm right margins, chapter titles 32 mm from the top, justified
  9 pt text with bold run-in labels, 8.5 pt tables. Figures carry the finding as their title, a
  small source line and a caption. Contents entries link to their pages and the PDF has bookmarks.
- The title page keeps a full-bleed photo (trip reports are not technical documents) but nothing is
  set over it: the report header sits in its own asphalt block below, as the system asks.
- Orange text uses `accent-text` (never `brand`) and appears on table row names and day dates;
  `brand` is for fills, plot series and the one accent stat.
- Dark mode (`tripreport build --mode dark`) swaps every token for its dark value. The
  `surface-inverse` title block follows the tokens and so turns light in dark mode.

`brand-book.md`, `plots.md` and `components/` are the design system's own documents, kept here for
reference. Change the system in its source and copy the files again; do not edit them here.
