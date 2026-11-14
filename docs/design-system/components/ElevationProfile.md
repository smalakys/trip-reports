# ElevationProfile

Altitude against distance (or time) for a single climb, filled to the baseline, with the start and summit called out.

- The consumer provides points `[distance_km, altitude_m]` (GPX track, resampled to ~200 points), start and summit names, and a finding for the title ("1,435 m of climbing in 3.4 km").
- Line `series-1` 2px, fill `chart-area`, gridlines `chart-grid` every 500 m, baseline `line-strong`. Ticks in `tick`, thousands separators.
- Start: muted label. Summit: altitude in `peak` weight, no box, no arrow.
- y axis starts at a round number below the lowest point, not at 0.
- A second track (planned route, previous attempt) goes `series-3` dashed, with no fill.
- In matplotlib or Plotly use the styles in the Plots section; the result should match this preview.
