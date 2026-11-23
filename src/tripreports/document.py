"""Turn a trip + analysis into a language-specific *document model*: a flat list of blocks.

The ReportLab renderer (render.py) is a dumb renderer of these blocks; every decision about *what* appears in
the report (sections, tables, wording, number formats) is made here and is unit-testable.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from .analysis import Analysis, resting
from .i18n import Locale
from .schema import Trip, resolve
from .theme import text_width_mm

_TOKEN = re.compile(r"(\*\*.+?\*\*|\*.+?\*)", re.S)


def rich(text: str) -> list[list[dict]]:
    """Parse 'blank line = paragraph, **bold**, *italic*' into paragraphs of runs."""
    paras = []
    for chunk in re.split(r"\n\s*\n", text.strip()):
        chunk = re.sub(r"[ \t\r\n]+", " ", chunk).strip()   # keeps non-breaking spaces (str.split would not)
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
    alt_chart: str | None = None        # expedition altitude chart (trips with a base camp)
    alt_chart_ratio: float = 0.0


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


def badge(grade: str, system: str | None = None, key: bool = False, ski: bool = False) -> dict:
    """A grade pill. ``key``: filled orange (the route's own grade); ``ski``: filled glacier blue (a ski
    mountaineering grade); neither: outlined."""
    return {"grade": grade, "system": system or "", "key": key, "ski": ski}


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
    if trip.grade:        # the grade of the whole route, after the class
        badges.append(badge(trip.grade, trip.grade_system or "Alpine"))
    if trip.ski_grade:
        badges.append(badge(trip.ski_grade, trip.ski_grade_system or "Toponeige", ski=True))
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

    # ---- route information -----------------------------------------------------------------
    h1(ui("route"), newpage=True)
    h2(ui("general"))      # the route and team at a glance: what the association reads first
    def run(t, b=False, m=False):
        return {"t": t, "b": b, "m": m}

    def bold(text):
        return {"lines": [[run(text, b=True)]]}

    # the main facts are bold, so the eye finds them among the details
    rows = [[ui("route_name"), bold(title)]]     # the route first; the date and the team, which change, last
    if trip.kind:
        rows.append([ui("class"), {"lines": [[run(L(trip.kind), b=True)]
                                              + ([run(f" ({L(trip.kind_note)})")] if trip.kind_note else [])]}])
    if trip.grade:
        rows.append([ui("grade"), bold(trip.grade + (", " + ui("ski_grade_inline").format(grade=trip.ski_grade)
                                                      if trip.ski_grade else ""))])
    elif trip.ski_grade:
        rows.append([ui("grade"), bold(ui("ski_grade_inline").format(grade=trip.ski_grade))])
    rows.append([ui("region"), bold(", ".join(x for x in (L(trip.country), L(trip.region)) if x))])
    if trip.peaks:
        rows.append([ui("peaks"), {"lines": [
            [run(p.name, b=True), run(
                f" ({loc.metres(p.elevation_m)})"
                + (f" – {p.grade}" if p.grade else "")
                + ((", " if p.grade else " – ") + ui("ski_grade_inline").format(grade=p.ski_grade)
                   if p.ski_grade else "")
                + (", " + ui("former_name").format(name=p.former_name) if p.former_name else ""))]
            for p in trip.peaks]}])
    people = []
    for person in trip.participants:
        if people:
            people.append([])                    # a gap between people
        contact = None if person.reporter else person.contact   # the author's contact is in the footnote
        extra = "; ".join(x for x in (L(person.note) if person.note else None, contact) if x)
        tail = (f" ({extra})" if extra else "") + (f" – {ui('leader')}" if person.leader else "")
        people.append([run(person.name, b=True)] + ([run(tail)] if tail else []))
        if person.bio:                           # the background is grey: it supports the names
            people.append([run(L(person.bio), m=True)])
        if person.experience:
            people.append([run(", ".join(person.experience), m=True)])
    rows.append([ui("date"), bold(loc.date_range(trip.start_date, trip.end_date))])
    if people:
        rows.append([ui("participants"), {"lines": people}])
    if trip.references:
        rows.append([ui("references"), "\n".join(trip.references)])
    general = _kv_table(loc, rows)
    authors = [p for p in trip.participants if p.reporter]
    if authors:       # the author's contact goes in a footnote under the table
        a = authors[0]
        general["after"] = [[{"t": (ui("reporter_contact").format(contact=a.contact) if a.contact
                                            else ui("reporter")), "b": False, "i": False}]]
        general["after_style"] = "footnote"
    blocks.append(general)

    if trip.route_description:
        h2(ui("route_description"))
        blocks.append({"type": "paras", "paras": rich(L(trip.route_description))})

    if trip.routes:
        h2(ui("route_sections"))
        has_pitches = any(s.pitches for g in trip.routes for s in g.sections)
        has_leader = any(s.leader for g in trip.routes for s in g.sections)
        has_note = any(s.note for g in trip.routes for s in g.sections) or any(g.note for g in trip.routes)
        has_grade = any(s.grade for g in trip.routes for s in g.sections) or any(
            g.grade or g.ski_grade for g in trip.routes)
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
            badges = ([badge(g.grade, g.grade_system, key=True)] if g.grade else []) + (
                [badge(g.ski_grade, g.ski_grade_system, ski=True)] if g.ski_grade else [])
            if not (len(trip.routes) > 1 or badges or g.note):   # a lone, unadorned route needs no heading row
                pass
            elif has_grade:     # the route's own row: its grade in the grade column, its note under notes
                row = [{"text": g.name, "heading": True}, {"badges": badges} if badges else ""]
                row += [""] * (has_pitches + has_leader)
                if has_note:
                    row.append(L(g.note))
                trows.append(row)
            else:
                trows.append([{"group": True, "span": len(cols), "text": g.name, "badges": [], "note": L(g.note)}])
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

    if trip.route_conditions:
        h2(ui("route_conditions"))
        blocks.append({"type": "paras", "paras": rich(L(trip.route_conditions))})

    # ---- preparation and logistics ---------------------------------------------------------
    has_gear = bool(trip.gear or trip.team_gear or trip.personal_gear)
    if trip.acclimatisation or trip.tactics or has_gear or trip.accommodation or trip.accommodation_intro \
            or trip.camps or trip.support:
        h1(ui("preparation"), newpage=True)
    if trip.acclimatisation:
        h2(ui("acclimatisation"))
        blocks.append({"type": "paras", "paras": rich(L(trip.acclimatisation))})
    if trip.tactics:
        h2(ui("tactics"))
        blocks.append({"type": "paras", "paras": rich(L(trip.tactics))})
    if has_gear:
        h2(ui("gear"))
        if trip.gear:
            blocks.append({"type": "bullets", "items": [L(g) for g in trip.gear]})
        # team and personal gear: one paragraph each, a bold run-in label and the items in a sentence
        gear_paras = []
        for key, items in (("team_gear", trip.team_gear), ("personal_gear", trip.personal_gear)):
            if items:
                listed = ", ".join(L(g).strip().rstrip(".") for g in items) + "."
                gear_paras.append([{"t": ui(key) + ": ", "b": True, "i": False},
                                   {"t": listed, "b": False, "i": False}])
        if gear_paras:
            blocks.append({"type": "paras", "paras": gear_paras})
    if trip.accommodation or trip.accommodation_intro or trip.camps:
        h2(ui("accommodation"))
        if trip.accommodation_intro:
            blocks.append({"type": "paras", "paras": rich(L(trip.accommodation_intro))})
        groups: list[str | None] = []
        for camp in trip.camps:                      # one table per mountain, in the order given
            if camp.group not in groups:
                groups.append(camp.group)
        has_pos = any(cp.lat is not None for cp in trip.camps)
        for group in groups:                         # a subsection per mountain, its name not repeated in the table
            if group:
                blocks.append({"type": "h3", "text": group})
            # short codes (C1, C2a) get a narrow column; named places (a hut, a glacier) a wider one
            name_w = 0.75 if all(len(cp.name) <= 5 for cp in trip.camps) else 1.5
            cols = [{"header": ui("camp"), "align": "left", "width": name_w},
                    {"header": ui("altitude"), "align": "right", "width": 0.85}]
            if has_pos:     # dot decimals in every language, so they paste straight into a map
                cols.append({"header": ui("coordinates"), "align": "left", "width": 1.85})
            cols.append({"header": ui("notes"), "align": "left", "width": (3.9 if has_pos else 4.6) + 0.75 - name_w})
            crows = []
            for cp in (cp for cp in trip.camps if cp.group == group):
                row = [cp.name, loc.metres(cp.altitude_m) if cp.altitude_m else ""]
                if has_pos:
                    row.append(f"{cp.lat:.6f}, {cp.lon:.6f}" if cp.lat is not None and cp.lon is not None else "")
                crows.append(row + [L(cp.note)])
            blocks.append(_table(cols, crows, key_first=True))
        # with a base camp the nights are a column of the daily table instead
        if trip.accommodation and not trip.base_camp:
            cols = [{"header": ui("night"), "align": "left", "width": 1.3},
                    {"header": ui("place"), "align": "left", "width": 2.2},
                    {"header": ui("type"), "align": "left", "width": 1.2},
                    {"header": ui("altitude"), "align": "right", "width": 1.0}]
            has_note = any(a.note for a in trip.accommodation)
            if has_note:
                cols.insert(3, {"header": ui("notes"), "align": "left", "width": 2.4})
            arows = []
            group = None
            for a in sorted(trip.accommodation, key=lambda a: a.date):
                if a.group and a.group != group:    # a heading row whenever the group changes
                    arows.append([{"group": True, "span": len(cols), "text": a.group, "badges": [],
                                   "note": ""}])
                group = a.group
                row = [loc.short_date(a.date), a.place, L(a.kind)]
                if has_note:
                    row.append(L(a.note))
                row.append(loc.metres(a.altitude_m) if a.altitude_m else "")
                arows.append(row)
            blocks.append(_table(cols, arows, key_first=True))
    if trip.support:
        h2(ui("support"))
        blocks.append({"type": "paras", "paras": rich(L(trip.support))})

    # ---- progress --------------------------------------------------------------------------
    if trip.days or trip.conditions or trip.diary_intro:
        h1(ui("progress"), newpage=True)
        if trip.diary_intro:
            blocks.append({"type": "paras", "paras": rich(L(trip.diary_intro))})
        if trip.conditions:     # the weather, before the days it explains
            h2(ui("conditions"))
            blocks.append({"type": "paras", "paras": rich(L(trip.conditions))})
        for d in sorted(trip.days, key=lambda d: d.date):
            h2(L(d.title), prefix=loc.short_date(d.date))
            by_date = next((x for x in an.days if x.date == d.date), None)
            blocks.append({"type": "paras", "paras": rich(fill_day_numbers(L(d.text), by_date, loc)),
                           "diary": True})

    # ---- timing ----------------------------------------------------------------------------
    h1(ui("timing"), newpage=True)
    timed = [p for p in an.peaks if p.time is not None]
    if timed:
        h2(ui("summit_log"))
        cols = [{"header": ui("peak"), "align": "left", "width": 2.4},
                {"header": ui("altitude"), "align": "right", "width": 1.2},
                {"header": ui("date"), "align": "left", "width": 1.8},
                {"header": ui("time"), "align": "right", "width": 0.9}]
        by_name = {p.name: p for p in trip.peaks}
        has_grade = any(p.grade for p in trip.peaks)
        has_ski = any(p.ski_grade for p in trip.peaks)
        if has_ski:
            cols.insert(1, {"header": ui("ski_grade"), "align": "left", "width": 1.75})
        if has_grade:
            cols.insert(1, {"header": ui("grade"), "align": "left", "width": 1.3})
        if has_grade or has_ski:
            cols[0]["width"] = 1.9
        # who reached each summit, only when not everyone reached every one
        team = [x.name for x in trip.participants]
        climbers = {p.name: p.climbers or team for p in trip.peaks}
        has_climbers = any(climbers.get(p.name, team) != team for p in timed)
        if has_climbers:
            cols.insert(len(cols) - 2, {"header": ui("climbers"), "align": "left", "width": 2.6})
            if has_grade or has_ski:    # a full table: make room so no header wraps
                for c, w in zip(cols, [1.6] + [None] * (len(cols) - 5) + [1.05, 1.9, 1.3, 1.0]):
                    c["width"] = w or c["width"]
                if has_grade:
                    cols[1]["width"] = 1.7

        def grades(name):
            p = by_name.get(name)
            out = []
            if has_grade:
                out.append({"badge": badge(p.grade, p.grade_system, key=True)} if p and p.grade else "")
            if has_ski:
                out.append({"badge": badge(p.ski_grade, p.ski_grade_system, ski=True)} if p and p.ski_grade else "")
            return out

        rows = [[p.name] + grades(p.name) + [loc.metres(p.elevation_m)]
                + ([", ".join(climbers.get(p.name, team))] if has_climbers else [])
                + [loc.short_date(p.time.date()), loc.clock(p.time)]
                for p in sorted(timed, key=lambda p: p.time)]
        blocks.append(_table(cols, rows, key_first=True))
    h2(ui("daily"))
    bc = trip.base_camp
    if bc:
        stay = loc.fig("daily_intro").format(
            days=loc.days(n_days), range=loc.date_range(trip.start_date, trip.end_date),
            bc_days=loc.days((bc.departure - bc.arrival).days + 1), bc_range=loc.date_range(bc.arrival, bc.departure))
        blocks.append({"type": "paras", "paras": rich(stay)})
    widths = ((("duration", 0.9), ("distance", 1.1), ("ascent", 1.1), ("descent", 1.3), ("min_alt", 1.35),
               ("max_alt", 1.4)) if bc else
              (("duration", 0.9), ("distance", 1.0), ("ascent", 1.1), ("descent", 1.3), ("min_alt", 1.4),
               ("max_alt", 1.4)))
    cols = [{"header": ui("date"), "align": "left", "width": 1.25 if bc else 1.5}] + (
        [{"header": ui("acc_sleep"), "align": "left", "width": 1.1}] if bc else []) + [
        {"header": ui(k), "align": "right", "width": w} for k, w in widths]
    slept = {a.date: a.place for a in trip.accommodation}

    def night(date):    # where the night after ``date`` was spent, during a base camp stay
        return slept.get(date, ui("bc_short")) if bc and bc.arrival <= date < bc.departure else ""

    tracked = {d.date: [loc.short_date(d.date)] + ([night(d.date)] if bc else []) + [
                   loc.duration(d.duration), loc.km(d.distance_m), loc.gain(d.ascent_m), loc.gain(-d.descent_m),
                   loc.metres(d.min_alt_m), loc.metres(d.max_alt_m)] for d in an.days}
    rows = list(tracked.values())
    if bc:     # every day of the stay; one without a track is greyed out with what it was
        rows = []
        date = min([bc.arrival, *tracked])
        while date <= max([bc.departure, *tracked]):
            if date in tracked:
                rows.append(tracked[date])
            elif bc.arrival <= date <= bc.departure:
                if date == bc.departure:
                    what = ui("bc_departure")
                elif date == bc.arrival:
                    what = ui("bc_arrival")
                else:
                    what = ui("rest_day") if resting(trip, date) else ui("no_track")
                rows.append([{"text": loc.short_date(date), "muted": True}, {"text": night(date), "muted": True},
                             {"text": what, "muted": True, "span": len(cols) - 2}])
            date += dt.timedelta(days=1)
    total = [ui("total")] + ([""] if bc else []) + [
        loc.duration(t["net_time"]), loc.km(t["distance_m"]), loc.gain(t["ascent_m"]),
        loc.gain(-t["descent_m"]), loc.metres(t["min_alt_m"]), loc.metres(t["max_alt_m"])]
    rows.append([{"text": v, "bold": True} for v in total])
    daily_table = _table(cols, rows, key_first=True, total_row=True)
    blocks.append(daily_table)
    if assets.alt_chart and an.expedition:     # the whole stay at a glance, right after its table
        above = [d.night_m for d in an.expedition if d.night_m is not None and d.night_m > bc.altitude_m]
        blocks.append({
            "type": "figure",
            "headline": loc.fig("alt_title").format(nights=loc.plural(len(above), "nights"),
                                                    highest=loc.metres(max(above, default=bc.altitude_m))),
            "subtitle": loc.fig("alt_subtitle"),
            "image": assets.alt_chart, "ratio": assets.alt_chart_ratio,
            "source": "", "caption": "",
        })
    if assets.acc:
        blocks.append({
            "type": "figure",
            "headline": loc.fig("acc_title").format(delta=loc.metres(assets.acc_delta_m)),
            "subtitle": loc.fig("acc_subtitle"),
            "image": assets.acc, "ratio": assets.acc_ratio,
            "source": "", "caption": loc.fig("acc_caption"),
        })
    if trip.gpx_note:     # after the table (and its charts): their figures come from the track
        if blocks[-1] is daily_table:     # no chart between: the note stays on the table's page
            daily_table["after"] = rich(loc.fig("gpx_note"))
        else:
            blocks.append({"type": "paras", "paras": rich(loc.fig("gpx_note"))})
    # the map and the profile, after the tables: they show the same recorded track
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
        for g, f in zip(an.groups, assets.groups, strict=True):
            blocks.append({"type": "figure_group", "title": L(g.name), "newpage": False,
                           "figures": map_and_profile(f.route_map, f.route_map_under, f.route_map_ratio,
                                                      f.profile, f.profile_ratio, g.distance_m, g.ascent_m,
                                                      g.n_days)})
    else:     # the map and the profile share one page, under their own heading
        blocks.append({"type": "figure_group", "title": ui("route_maps"), "newpage": False,
                       "figures": map_and_profile(assets.route_map, assets.route_map_under, assets.route_map_ratio,
                                  assets.profile, assets.profile_ratio, t["distance_m"], t["ascent_m"], n_days)})

    # ---- remarks and recommendations -------------------------------------------------------
    if trip.recommendations:
        h1(ui("recommendations"), newpage=True)
        blocks.append({"type": "paras", "paras": rich(L(trip.recommendations))})

    # ---- photos ----------------------------------------------------------------------------
    if trip.photos:
        h1(ui("photos"), newpage=True)
        tw = text_width_mm(theme)
        page = theme["page"]
        page_h = page["height_mm"] - page["margin_top_mm"] - page["margin_bottom_mm"]
        heading_room = 32   # the section heading shares the first photo page
        cap_room = 18       # caption (up to two lines) and gap under each photo
        # Photos keep their own aspect ratio (never cropped). Landscape photos go two to a page,
        # a portrait or "full" photo gets a page of its own.
        groups: list[list] = []
        cur: list = []
        for photo, (_path, (pw, ph)) in zip(trip.photos, assets.photos, strict=True):
            solo = photo.size == "full" or pw / ph < 1.3
            entry = (photo, _path, pw / ph, solo)
            if solo:
                if cur:
                    groups.append(cur)
                    cur = []
                groups.append([entry])
            else:
                cur.append(entry)
                if len(cur) == 2:
                    groups.append(cur)
                    cur = []
        if cur:
            groups.append(cur)
        pages = []
        for gi, grp in enumerate(groups):
            room = heading_room if gi == 0 else 0
            per = max(len(grp), 2) if not grp[0][3] else 1
            h_max = (page_h - room) / per - cap_room
            pages.append([{"size": photo.size, "image": _path, "w_mm": round(min(tw, h_max * aspect), 2),
                           "h_mm": None, "caption": L(photo.caption)}
                          for photo, _path, aspect, _solo in grp])
        blocks.append({"type": "photo_pages", "pages": pages})

    people_names = ", ".join(p.name for p in trip.participants)
    return {
        "lang": lang,
        "theme": theme,
        "meta": {"title": title, "author": people_names},
        "cover": cover,
        "blocks": blocks,
    }
