"""Turn a trip + analysis into a language-specific *document model*: a flat list of blocks.

The ReportLab renderer (render.py) is a dumb renderer of these blocks; every decision about *what* appears in
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
    """Files the builder has prepared, relative to the build folder."""

    cover: str
    cover_px: tuple[int, int]
    route_map: str
    route_map_ratio: float
    profile: str
    profile_ratio: float
    route_map_under: str | None = None     # basemap image drawn beneath the vector route map
    map_attribution: str | None = None
    acc: str | None = None
    acc_ratio: float = 0.0
    acc_delta_m: float = 0.0
    photos: list[tuple[str, tuple[int, int]]] = field(default_factory=list)
    groups: list[GroupFigures] = field(default_factory=list)   # one map and profile per figure group


@dataclass
class GroupFigures:
    """The route map and elevation profile prepared for one figure group."""

    route_map: str
    route_map_ratio: float
    profile: str
    profile_ratio: float
    route_map_under: str | None = None


def _table(columns, rows, **extra):
    return {"type": "table", "columns": columns, "rows": rows, **extra}


def _kv_table(loc: Locale, rows):
    cols = [{"header": "", "align": "left", "width": 1.0},
            {"header": "", "align": "left", "width": 2.6}]
    return _table(cols, rows, key_first=True)


_DAY_TOKEN = re.compile(r"\{(distance|ascent|descent|duration|hours|max_alt|min_alt)\}")


def fill_day_numbers(text: str, stats, loc: Locale) -> str:
    """Replace {distance}, {ascent}, {descent}, {duration}, {hours}, {max_alt}, {min_alt} in a day's text
    with that day's figures from the track, so the diary and the tables never disagree."""
    if stats is None:
        return text
    values = {
        "distance": loc.km(stats.distance_m), "ascent": loc.metres(round(stats.ascent_m, -1)),
        "descent": loc.metres(round(stats.descent_m, -1)), "duration": loc.duration(stats.duration),
        "hours": loc.hours(stats.duration), "max_alt": loc.metres(stats.max_alt_m),
        "min_alt": loc.metres(stats.min_alt_m),
    }
    return _DAY_TOKEN.sub(lambda m: values[m.group(1)], text)


def badge(grade: str, system: str | None = None, key: bool = False) -> dict:
    return {"grade": grade, "system": system or "", "key": key}


def build_document(trip: Trip, an: Analysis, assets: Assets, theme: dict, lang: str) -> dict:
    loc = Locale(lang)
    fallbacks = trip.languages

    def L(text):
        return resolve(text, lang, fallbacks)

    ui = loc.ui
    title = L(trip.title)
    n_days = (trip.end_date - trip.start_date).days + 1
    t = an.totals
    blocks: list[dict] = []

    def h1(text, newpage=False):
        blocks.append({"type": "h1", "text": text, "newpage": newpage})

    def h2(text, prefix=""):
        blocks.append({"type": "h2", "text": text, "prefix": prefix})

    # ---- title page data -------------------------------------------------------------------
    highest = max((p.elevation_m for p in trip.peaks), default=t["max_alt_m"])
    available = {
        "highest_point": (loc.num(highest), ui("meters"), ui("highest_point")),
        "ascent": (loc.gain(t["ascent_m"]).replace(f"{ui('meters')}", "").strip(), ui("meters"), ui("ascent")),
        "descent": (loc.gain(-t["descent_m"]).replace(f"{ui('meters')}", "").strip(), ui("meters"),
                    ui("descent")),
        "distance": (loc.num(t["distance_m"] / 1000, 1), ui("kilometers"), ui("distance")),
        "peaks": (str(len(trip.peaks)), "", ui("peaks")),
        "days": (str(n_days), "", ui("days_stat")),
        "net_time": (loc.duration(t["net_time"]), "", ui("net_time")),
        "vertical_range": (loc.num(round(t["max_alt_m"] - t["min_alt_m"])), ui("meters"),
                           ui("vertical_range")),
    }
    stats = [{"value": available[k][0], "unit": available[k][1], "label": available[k][2],
              "accent": i == 0} for i, k in enumerate(trip.cover_stats)
             if k != "peaks" or trip.peaks]
    region = ", ".join(x for x in (L(trip.region), L(trip.country)) if x)
    badges = [badge(L(trip.kind), None, key=True)] if trip.kind else []   # the report's category
    cover = {
        "image": assets.cover,
        "association": ui("association"),
        "kind": L(trip.cover.kicker) or ui("report_kind"),
        "label": f"{region} · {loc.date_range(trip.start_date, trip.end_date)}",
        "title": title,
        "subtitle": L(trip.subtitle),
        "badges": badges,
        "stats": stats,
        "meta": [{"k": ui("date"), "v": loc.date_range(trip.start_date, trip.end_date)}] + (
            [{"k": ui("participants"), "v": ", ".join(p.name for p in trip.participants)}]
            if trip.participants else []),
    }

    # ---- contents --------------------------------------------------------------------------
    if trip.show_contents:
        blocks.append({"type": "contents", "title": ui("contents"), "newpage": True})

    # ---- general information ---------------------------------------------------------------
    h1(ui("general"), newpage=True)
    rows = [[ui("date"), loc.date_range(trip.start_date, trip.end_date)]]
    if trip.kind:
        rows.append([ui("class"), L(trip.kind)])
    rows.append([ui("region"), ", ".join(x for x in (L(trip.country), L(trip.region)) if x)])
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
    if people:
        rows.append([ui("participants"), "\n\n".join(people)])
    blocks.append(_kv_table(loc, rows))

    # ---- route information -----------------------------------------------------------------
    h1(ui("route"))
    if trip.route_description:
        h2(ui("route_description"))
        blocks.append({"type": "paras", "paras": rich(L(trip.route_description))})

    if trip.routes:
        h2(ui("route_sections"))
        has_pitches = any(s.pitches for g in trip.routes for s in g.sections)
        has_leader = any(s.leader for g in trip.routes for s in g.sections)
        has_note = any(s.note for g in trip.routes for s in g.sections)
        has_grade = any(s.grade for g in trip.routes for s in g.sections)
        cols = [{"header": ui("section"), "align": "left", "width": 2.0}]
        if has_grade:
            cols.append({"header": ui("grade"), "align": "left", "width": 1.45})
        if has_pitches:
            cols.append({"header": ui("pitches"), "align": "left", "width": 1.0})
        if has_leader:
            cols.append({"header": ui("participants"), "align": "left", "width": 1.2})
        if has_note:
            cols.append({"header": ui("notes"), "align": "left", "width": 2.2})
        trows = []
        for g in trip.routes:
            if len(trip.routes) > 1 or g.grade or g.note:   # a lone, unadorned route needs no heading row
                trows.append([{"group": True, "span": len(cols), "text": g.name,
                               "badge": badge(g.grade, g.grade_system, key=True) if g.grade else None,
                               "note": L(g.note)}])
            for s in g.sections:
                row = [s.name]
                if has_grade:
                    row.append({"badge": badge(s.grade)} if s.grade else "")
                if has_pitches:
                    row.append(s.pitches or "")
                if has_leader:
                    row.append(L(s.leader))
                if has_note:
                    row.append(L(s.note))
                trows.append(row)
        blocks.append(_table(cols, trows, key_first=True))

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
            blocks.append(_table(cols, arows, key_first=True))
        if trip.support:
            blocks.append({"type": "labeled", "items": [
                {"label": ui("support"), "paras": rich(L(trip.support))}]})

    # ---- timing ----------------------------------------------------------------------------
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
        blocks.append(_table(cols, rows, key_first=True))
    h2(ui("daily"))
    cols = [{"header": ui("date"), "align": "left", "width": 1.5}] + [
        {"header": ui(k), "align": "right", "width": w} for k, w in
        (("duration", 0.9), ("distance", 1.0), ("ascent", 1.1), ("descent", 1.3),
         ("min_alt", 1.4), ("max_alt", 1.4))]
    rows = [[loc.short_date(d.date), loc.duration(d.duration), loc.km(d.distance_m),
             loc.gain(d.ascent_m), loc.gain(-d.descent_m), loc.metres(d.min_alt_m),
             loc.metres(d.max_alt_m)] for d in an.days]
    total = [ui("total"), loc.duration(t["net_time"]), loc.km(t["distance_m"]), loc.gain(t["ascent_m"]),
             loc.gain(-t["descent_m"]), loc.metres(t["min_alt_m"]), loc.metres(t["max_alt_m"])]
    rows.append([{"text": v, "bold": True} for v in total])
    blocks.append(_table(cols, rows, key_first=True, total_row=True))

    # ---- progress --------------------------------------------------------------------------
    if trip.days or trip.acclimatisation:
        h1(ui("progress"))
        if trip.acclimatisation:
            h2(ui("acclimatisation"))
            blocks.append({"type": "paras", "paras": rich(L(trip.acclimatisation))})
        for d in sorted(trip.days, key=lambda d: d.date):
            h2(L(d.title), prefix=loc.short_date(d.date))
            by_date = next((x for x in an.days if x.date == d.date), None)
            blocks.append({"type": "paras", "paras": rich(fill_day_numbers(L(d.text), by_date, loc)),
                           "diary": True})

    # ---- figures ---------------------------------------------------------------------------
    h1(ui("figures"), newpage=True)
    source_map = ui("source_tiles").format(attribution=assets.map_attribution) if assets.map_attribution else ""

    def map_and_profile(route_map, under, map_ratio, profile, profile_ratio, distance_m, ascent_m, days):
        days_txt = loc.fig("single_day") if days == 1 else loc.days(days)
        return [{
            "type": "figure",
            "headline": loc.fig("route_title").format(distance=loc.km(distance_m, 0), days=days_txt),
            "subtitle": loc.fig("route_subtitle_single" if days == 1 else "route_subtitle"),
            "image": route_map, "under": under, "ratio": map_ratio,
            "source": source_map, "caption": "",
        }, {
            "type": "figure",
            "headline": loc.fig("profile_title").format(ascent=loc.gain(ascent_m), days=days_txt),
            "subtitle": loc.fig("profile_subtitle"),
            "image": profile, "ratio": profile_ratio,
            "source": "", "caption": "",
        }]

    if an.groups:
        for i, (g, f) in enumerate(zip(an.groups, assets.groups, strict=True)):
            blocks.append({"type": "figure_group", "title": L(g.name), "newpage": i > 0,
                           "figures": map_and_profile(f.route_map, f.route_map_under, f.route_map_ratio,
                                                      f.profile, f.profile_ratio, g.distance_m, g.ascent_m,
                                                      g.n_days)})
    else:
        blocks += map_and_profile(assets.route_map, assets.route_map_under, assets.route_map_ratio,
                                  assets.profile, assets.profile_ratio, t["distance_m"], t["ascent_m"], n_days)
    if assets.acc:
        blocks.append({
            "type": "figure",
            "headline": loc.fig("acc_title").format(delta=loc.metres(assets.acc_delta_m)),
            "subtitle": loc.fig("acc_subtitle"),
            "image": assets.acc, "ratio": assets.acc_ratio,
            "source": "", "caption": loc.fig("acc_caption"),
        })

    # ---- photos ----------------------------------------------------------------------------
    if trip.photos:
        h1(ui("photos"), newpage=True)
        tw = text_width_mm(theme)
        page = theme["page"]
        page_h = page["height_mm"] - page["margin_top_mm"] - page["margin_bottom_mm"]
        heading_room = 40  # the section heading shares the first photo page
        items = []
        for k, (photo, (_path, (pw, ph))) in enumerate(zip(trip.photos, assets.photos, strict=True)):
            aspect = pw / ph
            room = heading_room if k == 0 else 0
            if photo.size == "full":
                w, h = min(tw, (page_h - 30 - room) * aspect), None
            elif aspect >= 1.3:      # landscape: full text width, lightly cropped to fit two per page
                w, h = tw, 108.0
            else:                    # portrait: centred, scaled to fit
                w, h = min(tw, 108.0 * aspect), None
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
        h1(ui("references"), newpage=True)
        blocks.append({"type": "bullets", "items": trip.references, "plain": True})

    people_names = ", ".join(p.name for p in trip.participants)
    return {
        "lang": lang,
        "theme": theme,
        "meta": {"title": title, "author": people_names},
        "cover": cover,
        "blocks": blocks,
    }
