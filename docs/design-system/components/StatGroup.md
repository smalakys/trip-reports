# StatGroup

The three to five numbers that sum up a climb, set large in a row: the first thing on every report, activity card and summit page.

- Markup: `.laa-stats` containing `.laa-stat` items, each a `.laa-label` then `.laa-stat__value` with an optional `.laa-stat__unit`.
- The consumer provides label (uppercase via the class, written in sentence case) and the formatted value: thousands separator, `+` for gain, `h:mm` for durations.
- Mark at most one stat `laa-stat--accent` (it turns `brand`): usually the summit altitude. Orange numbers are 40px, above the 3:1 large-text floor.
- Items are separated by a `line` hairline and wrap on narrow screens.
- Don't: show more than five, mix units in one value, or round altitudes to the nearest hundred.
