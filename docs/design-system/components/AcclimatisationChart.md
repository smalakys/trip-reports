# AcclimatisationChart

Expedition overview: the day's high point against the altitude slept at, so the climb-high-sleep-low rhythm and the summit push read at a glance.

- The consumer provides one row per day: `day`, `high_m`, `sleep_m`, plus optional events (rest day, storm, summit) and the summit altitude.
- High point is `series-1` with `chart-area` fill; sleeping altitude is `series-2` (glacier blue), lines only. Both 2px.
- Label the two lines directly at their right end in their own colour; no legend.
- Call out the summit with a hollow dot and its altitude in `peak` weight. Rest days or storm days may be shaded with a `surface-200` band behind the grid, labelled in `lbl-muted`.
- y axis from a round number below base camp; ticks every 1,500 m in `tick`.
- Don't: add a third altitude line (use a separate plot), or colour the summit day green.
