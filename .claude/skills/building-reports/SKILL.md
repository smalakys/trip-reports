---
name: building-reports
description: How to build a trip report PDF in this repo. Every build must also produce the lightweight web copy (report-<lang>-web.pdf, for email and the web) next to the full-quality PDF. Use it whenever you run `tripreport build`, rebuild a report after an edit, or hand a finished report to the user.
---

# Building a report: always both PDFs

A build writes two files in `<trip>/out/`:

- `report-<lang>.pdf`: full quality, to print and archive.
- `report-<lang>-web.pdf`: the lightweight copy (photos at 200 ppi, Ghostscript), to email and put on the web.

**The web copy is part of every report.** The user expects both after every build, so never leave an old
one behind.

## Rules

1. Run `.venv/bin/tripreport build <trip-dir> --lang <lang> ...` **without `--no-web`**. The flag exists
   only for throw-away experiments that never reach the user (a layout test, a quick PNG preview). If you
   used it while iterating, finish with one last build **without** it, so that both PDFs come from the
   same, final version of the trip.
2. After the last build, check that `out/report-<lang>-web.pdf` exists, is newer than the trip file and
   is much smaller than `out/report-<lang>.pdf`. The command prints its size ("for email and the web").
3. If it prints "no web copy written", Ghostscript is missing (`brew install ghostscript`). Do not call the
   report finished: install it or tell the user the web copy is missing and why.
4. Several languages: build each one (`--lang lt`, `--lang en`); each gets its own web copy.
5. In your final message name both files and their sizes.
6. `tripreport compress <src.pdf> [dst]` makes the web copy of a PDF that was built earlier.

`out/` is git-ignored: never commit either PDF.
