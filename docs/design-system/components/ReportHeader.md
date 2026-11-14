# ReportHeader

The opening block of every trip or expedition report: association band, region and date, peak, route, grade and outcome.

- Structure: a `surface-inverse` band with the tricolour strip and the association name in `label` / `ink-inverse`; then on `surface-000` a `label` line (range · ISO date), the peak in `display-l`, the route in `subtitle` / `ink-muted`, and a row of `GradeBadge`s with a one-line outcome.
- The consumer provides region, date, peak, route, grades, team size and outcome. Outcome is a plain sentence: "Summited 07:40" or "Turned back at 3,900 m"; a turnaround may add a `danger` word, never colour alone.
- Follow it directly with a `StatGroup`, then the narrative.
- Bilingual reports: Lithuanian label in the band, English in the body, or the reverse; never both on one line except the band.
- Don't: put a photo behind the title, or use the band more than once per page.
