# GradeBadge

A route's difficulty as a pill: grading system in small caps, then the grade exactly as the guidebook writes it.

- Markup: `<span class="laa-grade"><span class="laa-grade__sys">Alpine</span>AD+</span>`. Systems: `Alpine` (F–ED), `UIAA` (rock), `Cat.` (Russian/ex-USSR 1A–6B), or none for a slope angle.
- Add `laa-grade--key` to the one overall grade of a route; secondary pitches and slope angles stay outlined.
- The consumer provides the system and grade string; never convert between systems.
- `radius-pill` is reserved for this component and filter chips.
