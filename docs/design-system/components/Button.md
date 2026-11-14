# Button

Actions in the report app and on the website: one primary per view, the rest secondary or ghost.

- Markup: `<button class="laa-btn laa-btn--primary">`; variants `--primary`, `--secondary`, `--ghost`. Optional leading 18px Lucide icon as the first child.
- The consumer provides the label (verb first, sentence case: "New report", "Export PDF") and the handler.
- Primary fills with `action` and `on-action`; never `brand` with white text, which fails contrast in light.
- Secondary: `surface-000` with a `line-strong` border. Ghost: `accent-text`, for low-weight links like "View route".
- Height 40px, `radius-md`, focus ring 2px `accent-text` at 2px offset.
- Don't: put two primaries side by side, use a pill shape, or add shadows.
