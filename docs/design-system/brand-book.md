The visual system for the Lithuanian Mountaineering Association (LAA): expedition plots, trip reports, a report-building app and the alpinist.lt website. One orange, asphalt and chalk neutrals, sharp corners, numbers that read at a glance. The orange is `brand` (#fc4c02); the rest is built to sit next to it.

## Principles

- **The climb is the hero.** Altitude, elevation gain, time and grade are the content. Lead every report, card and screen with the numbers, then the story.
- **One orange.** `brand` marks what the page is about: the main series, the primary action, the active tab. If two things on a screen are orange, one of them is wrong.
- **Flat and sharp.** No gradients, no shadows on cards in flow, corners at `radius-md` (4px) or less. Hierarchy comes from `surface-*` steps, `line` and type weight.
- **Bilingual by default.** Lithuanian first, English second, as on the membership card (`galioja iki // valid until`). Every font in this system covers ą č ę ė į š ų ū ž.

## Content fundamentals

- Write like a route log: short declarative sentences, past tense for what happened, times in 24h (`01:30`), dates ISO (`2026-06-04`).
- Units: metres with a thin space and thousands separator (`7,495 m`, LT: `7 495 m`), elevation gain as `+2,140 m`, durations as `11:42` (h:mm). Never feet.
- Grades as written in the guidebook: alpine `PD`, `AD+`, `D`, `TD-`, `ED`; rock UIAA `V+`; Russian categories `5A`. Set them in `GradeBadge`.
- Casing: sentence case for headings ("Summit day", "Acclimatisation profile"); uppercase only in `label`.
- Voice: "we" for the team, names for individuals. No emoji in reports or the site.

## Colour

- Page: `surface-100`. Cards, report pages and plot backgrounds: `surface-000`. Wells and table headers: `surface-200`.
- Text: `ink` for everything that matters, `ink-muted` for labels, captions and axis ticks. On `surface-inverse` use `ink-inverse`.
- Orange text is `accent-text`, never `brand`: `brand` is 3.4:1 on white, fine for fills, marks and 24px+ display text, not for small type.
- Buttons and filled controls use `action` with `on-action` text. In light, `action` is a deeper orange (#cc4200) so white labels pass; in dark it is `brand` with dark text.
- Status (`success`, `warning`, `danger`) always carries a word: "Summited", "Turned back at 6,800 m". Never colour alone.
- The tricolour (`flag-yellow`, `flag-green`, `flag-red`) appears only as the three-band strip from the membership card: report covers, website footer. Never as text, chart series or status.
- Focus ring: 2px solid `accent-text`, 2px offset, on every interactive element.

## Type

- Three Barlow cuts, all on Google Fonts: `display` (Barlow Condensed 700) for titles, `sans` (Barlow) for text, `numeric` (Barlow Semi Condensed 600) for stats and axis ticks.
- Load: `https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@700&family=Barlow+Semi+Condensed:wght@500;600&display=swap`.
- Use `display-xl` once per page. Report sections: `display-l` → `title` → `body`.
- Every number in a stat, table or axis sets `font-variant-numeric: tabular-nums`.
- `label` is always uppercase with its letter-spacing.

## Space, radius, layout

- 4px base. Card padding `space-6` (desktop) / `space-4` (mobile). Between report sections `space-8`.
- `radius-md` for buttons and cards, `radius-sm` for inputs and bars, `radius-pill` only for `GradeBadge` and chips.
- Reports: A4 portrait, single column of text at max 680px with plots full width. Website and app: 1120px max content width, 16px mobile gutter.
- `shadow-float` only on menus, tooltips and the plot hover card.

## Plots

The full plotting rules and ready-to-use matplotlib and Plotly styles are in the **Plots** section. In short: `series-1` (orange) is the series the plot is about, `series-2` (glacier blue) is the comparison, `chart-grid` horizontal gridlines only, direct labels instead of legends, `tick` for all numbers.

## Iconography

- No icon set ships with the LAA. Use Lucide (`lucide@0.460.0`, 1.5px stroke, 20px) for UI icons: `mountain`, `mountain-snow`, `tent`, `route`, `clock`, `thermometer`, `wind`, `flag`.
- Icons take `ink-muted` by default and `brand` only when active.
- No emoji as icons.

## Logo

- No vector logo was available; the association's mark is only on the printed card. Until the official file is uploaded under assets/Logos, set the name in `display` type ("LAA" or "Lietuvos alpinizmo asociacija") with the tricolour strip beside it. Do not redraw the mark.
