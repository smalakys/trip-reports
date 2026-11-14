"""Turn a trip + analysis into a language-specific *document model*: a flat list of blocks.

The Typst template is a dumb renderer of these blocks; every decision about *what* appears in
the report (sections, tables, wording, number formats) is made here and is unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .analysis import Analysis
from .i18n import Locale
from .schema import Trip, resolve
from .theme import text_width_mm

_TOKEN = re.compile(r"(\*\*.+?\*\*|\*.+?\*)", re.S)


def rich(text: str) -> list[list[dict]]:
    """Parse 'blank line = paragraph, **bold**, *italic*' into paragraphs of runs."""
    paras = []
    for chunk in re.split(r"\n\s*\n", text.strip()):
        chunk = " ".join(chunk.split())
        runs = []
        for part in _TOKEN.split(chunk):
            if not part:
                continue
            if part.startswith("**") and part.endswith("**") and len(part) > 4:
                runs.append({"t": part[2:-2], "b": True, "i": False})
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                runs.append({"t": part[1:-1], "b": False, "i": True})
            else:
                runs.append({"t": part, "b": False, "i": False})
        if runs:
            paras.append(runs)
    return paras


@dataclass
class Assets:
    """Files the builder has prepared, relative to the Typst build folder."""

    cover: str
    cover_px: tuple[int, int]
    route_map: str
    route_map_ratio: float
    profile: str
    profile_ratio: float
    photos: list[tuple[str, tuple[int, int]]] = field(default_factory=list)


def _table(caption, columns, rows, **extra):
    return {"type": "table", "caption": caption, "columns": columns, "rows": rows, **extra}


def _kv_table(caption, loc: Locale, rows):
    cols = [{"header": loc.ui("parameter"), "align": "left", "width": 1.0},
            {"header": loc.ui("value"), "align": "left", "width": 2.6}]
    return _table(caption, cols, rows, key_first=True)


def build_document(trip: Trip, an: Analysis, assets: Assets, theme: dict, lang: str) -> dict:
    loc = Locale(lang)
    fallbacks = trip.languages

    def L(text):
        return resolve(text, lang, fallbacks)

    ui = loc.ui
    title = L(trip.title)
    n_days = (trip.end_date - trip.start_date).days + 1
    blocks: list[dict] = []

    def h1(text, numbered=True, newpage=False):
        blocks.append({"type": "h1", "text": text, "numbered": numbered, "newpage": newpage})

    def h2(text, numbered=True):
        blocks.append({"type": "h2", "text": text, "numbered": numbered})

    # ---- summary ---------------------------------------------------------------------------
    if trip.summary:
        h1(ui("summary"), numbered=False, newpage=True)
        blocks.append({"type": "labeled", "items": [
            {"label": L(s.label), "paras": rich(L(s.text))} for s in trip.summary]})
    if trip.show_contents:
        blocks.append({"type": "contents", "title": ui("contents")})

    # ---- 1 general information -------------------------------------------------------------
    h1(ui("general"), newpage=True)
    region = ", ".join(x for x in (L(trip.country), L(trip.region)) if x)
    rows = [[ui("date"), loc.date_range(trip.start_date, trip.end_date)]]
    if trip.kind:
        rows.append([ui("class"), L(trip.kind)])
    rows.append([ui("region"), region])
    if trip.peaks:
        rows.append([ui("peaks"), "\n".join(f"{p.name} ({loc.metres(p.elevation_m)})" for p in trip.peaks)])
    people = []
    for person in trip.participants:
        lines = [person.name]
        if person.experience:
            lines.append(", ".join(person.experience))
        if person.contact:
            lines.append(person.contact)
        people.append("\n".join(lines))
    rows.append([ui("participants"), "\n\n".join(people)])
    blocks.append(_kv_table(None, loc, rows))

    # ---- 2 route information ---------------------------------------------------------------
    h1(ui("route"))
    t = an.totals
    numbers = [
        [ui("min_max_alt"), f"{loc.metres(t['min_alt_m'])} – {loc.metres(t['max_alt_m'])}"],
        [ui("vertical_range"), loc.metres(t["max_alt_m"] - t["min_alt_m"])],
        [ui("total_distance"), loc.km(t["distance_m"])],
        [ui("total_ascent"), loc.metres(t["ascent_m"])],
        [ui("total_descent"), loc.metres(t["descent_m"])],
        [ui("net_time"), loc.hours(t["net_time"])],
        [ui("days_label"), str(n_days)],
    ]
    h2(ui("route_numbers"))
    blocks.append(_kv_table(None, loc, numbers))

    if trip.routes:
        h2(ui("route_sections"))
        has_pitches = any(s.pitches for g in trip.routes for s in g.sections)
        has_leader = any(s.leader for g in trip.routes for s in g.sections)
        has_note = any(s.note for g in trip.routes for s in g.sections)
        cols = [{"header": ui("section"), "align": "left", "width": 2.0},
                {"header": ui("grade"), "align": "left", "width": 1.0}]
        if has_pitches:
            cols.append({"header": ui("pitches"), "align": "left", "width": 1.0})
        if has_leader:
            cols.append({"header": ui("participants"), "align": "left", "width": 1.2})
        if has_note:
            cols.append({"header": ui("notes"), "align": "left", "width": 2.2})
        trows = []
        for g in trip.routes:
            head = g.name + (f"  ·  {g.grade}" if g.grade else "")
            trows.append([{"text": head, "bold": True, "span": len(cols), "group": True}])
            for s in g.sections:
                row = [s.name, s.grade or ""]
                if has_pitches:
                    row.append(s.pitches or "")
                if has_leader:
                    row.append(L(s.leader))
                if has_note:
                    row.append(L(s.note))
                trows.append(row)
        blocks.append(_table(None, cols, trows, key_first=False))

    if trip.tactics or trip.gear:
        h2(ui("tactics"))
        if trip.tactics:
            blocks.append({"type": "paras", "paras": rich(L(trip.tactics))})
        if trip.gear:
            blocks.append({"type": "bullets", "items": [L(g) for g in trip.gear]})
    if trip.conditions:
        h2(ui("conditions"))
        blocks.append({"type": "paras", "paras": rich(L(trip.conditions))})
    if trip.accommodation or trip.support:
        h2(ui("accommodation"))
        if trip.accommodation:
            cols = [{"header": ui("night"), "align": "left", "width": 1.3},
                    {"header": ui("place"), "align": "left", "width": 2.2},
                    {"header": ui("type"), "align": "left", "width": 1.2},
                    {"header": ui("altitude"), "align": "right", "width": 1.0}]
            has_note = any(a.note for a in trip.accommodation)
            if has_note:
                cols.insert(3, {"header": ui("notes"), "align": "left", "width": 2.4})
            arows = []
            for a in sorted(trip.accommodation, key=lambda a: a.date):
                row = [loc.short_date(a.date), a.place, L(a.kind)]
                if has_note:
                    row.append(L(a.note))
                row.append(loc.metres(a.altitude_m) if a.altitude_m else "")
                arows.append(row)
            blocks.append(_table(None, cols, arows, key_first=False))
        if trip.support:
            blocks.append({"type": "labeled", "items": [
                {"label": ui("support"), "paras": rich(L(trip.support))}]})

    # ---- 3 timing --------------------------------------------------------------------------
    h1(ui("timing"))
    timed = [p for p in an.peaks if p.time is not None]
    if timed:
        h2(ui("summit_log"))
        cols = [{"header": ui("peak"), "align": "left", "width": 2.4},
                {"header": ui("altitude"), "align": "right", "width": 1.2},
                {"header": ui("date"), "align": "left", "width": 1.8},
                {"header": ui("time"), "align": "right", "width": 0.9}]
        rows = [[p.name, loc.metres(p.elevation_m), loc.short_date(p.time.date()), loc.clock(p.time)]
                for p in sorted(timed, key=lambda p: p.time)]
        blocks.append(_table(None, cols, rows, key_first=True))
    h2(ui("daily"))
    cols = [{"header": ui("day"), "align": "left", "width": 1.7}] + [
        {"header": ui(k), "align": "right", "width": w} for k, w in
        (("duration", 1.0), ("distance", 1.1), ("ascent", 1.1), ("descent", 1.3),
         ("min_alt", 1.25), ("max_alt", 1.25))]
    rows = []
    for d in an.days:
        rows.append([loc.short_date(d.date), loc.duration(d.duration), loc.km(d.distance_m),
                     loc.metres(d.ascent_m), loc.metres(d.descent_m), loc.metres(d.min_alt_m),
                     loc.metres(d.max_alt_m)])
    rows.append([{"text": ui("total"), "bold": True}, {"text": loc.duration(t["net_time"]), "bold": True},
                 {"text": loc.km(t["distance_m"]), "bold": True},
                 {"text": loc.metres(t["ascent_m"]), "bold": True},
                 {"text": loc.metres(t["descent_m"]), "bold": True},
                 {"text": loc.metres(t["min_alt_m"]), "bold": True},
                 {"text": loc.metres(t["max_alt_m"]), "bold": True}])
    blocks.append(_table(None, cols, rows, key_first=True, total_row=True))

    # ---- 4 progress ------------------------------------------------------------------------
    if trip.days or trip.acclimatisation:
        h1(ui("progress"))
        if trip.acclimatisation:
            h2(ui("acclimatisation"))
            blocks.append({"type": "paras", "paras": rich(L(trip.acclimatisation))})
        for d in sorted(trip.days, key=lambda d: d.date):
            h2(f"{loc.short_date(d.date)} · {L(d.title)}")
            blocks.append({"type": "paras", "paras": rich(L(d.text)), "diary": True})

    # ---- 5 figures -------------------------------------------------------------------------
    h1(ui("figures"), newpage=True)
    days_txt = loc.days(n_days)
    source_map = ui("source_tiles") if trip.map.basemap == "tiles" else ui("source_track")
    blocks.append({
        "type": "figure",
        "headline": loc.fig("route_title").format(distance=loc.km(t["distance_m"], 0), days=days_txt),
        "subtitle": loc.fig("route_subtitle"),
        "image": assets.route_map, "ratio": assets.route_map_ratio,
        "source": source_map,
        "caption": loc.fig("route_caption"),
    })
    blocks.append({
        "type": "figure",
        "headline": loc.fig("profile_title").format(ascent=loc.metres(t["ascent_m"]), days=days_txt),
        "subtitle": loc.fig("profile_subtitle"),
        "image": assets.profile, "ratio": assets.profile_ratio,
        "source": ui("source_gpx"),
        "caption": loc.fig("profile_caption"),
    })

    # ---- 6 photos --------------------------------------------------------------------------
    if trip.photos:
        h1(ui("photos"), newpage=True)
        tw = text_width_mm(theme)
        page_h = theme["page"]["height_mm"] - theme["page"]["margin_top_mm"] - theme["page"]["margin_bottom_mm"]
        heading_room = 52  # the section heading shares the first photo page
        items = []
        for k, (photo, (_path, (pw, ph))) in enumerate(zip(trip.photos, assets.photos, strict=True)):
            aspect = pw / ph
            room = heading_room if k == 0 else 0
            if photo.size == "full":
                w, h = min(tw, (page_h - 34 - room) * aspect), None
            elif aspect >= 1.3:      # landscape: full text width, lightly cropped to fit two per page
                w, h = tw, 106.0
            else:                    # portrait: centred, scaled to fit
                w, h = min(tw, 106.0 * aspect), None
            items.append({"size": photo.size, "image": _path, "w_mm": round(w, 2), "h_mm": h,
                          "caption": L(photo.caption)})
        pages, cur = [], []
        for k, it in enumerate(items):
            if k == 0 and it["size"] == "half":
                pages.append([it])          # first page also holds the heading: one photo only
            elif it["size"] == "full":
                if cur:
                    pages.append(cur)
                    cur = []
                pages.append([it])
            else:
                cur.append(it)
                if len(cur) == 2:
                    pages.append(cur)
                    cur = []
        if cur:
            pages.append(cur)
        blocks.append({"type": "photo_pages", "pages": pages})

    if trip.references:
        h1(ui("references"), numbered=False, newpage=True)
        blocks.append({"type": "bullets", "items": trip.references, "plain": True})

    people = ", ".join(p.name for p in trip.participants)
    return {
        "lang": lang,
        "theme": theme,
        "meta": {"title": title, "author": people},
        "labels": {"table": ui("table"), "figure": ui("figure")},
        "cover": {
            "image": assets.cover,
            "kicker": L(trip.cover.kicker),
            "title": title,
            "subtitle": L(trip.subtitle),
            "meta": [
                {"k": loc.data["labels"]["cover_meta_date"], "v": loc.date_range(trip.start_date, trip.end_date)},
                {"k": loc.data["labels"]["cover_meta_team"], "v": people},
            ],
        },
        "blocks": blocks,
    }
