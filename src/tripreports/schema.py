"""The trip file schema: the contract between every front end (CLI, agents, apps) and the build.

Write trips as YAML (or JSON) that validates against `Trip`. The JSON Schema generated from
these models lives in ``schema/trip.schema.json`` and can drive forms in other front ends.

Text that readers see (titles, descriptions, diary entries, captions) is *localised*: either a
plain string, or a mapping of language code to string, e.g. ``{lt: "...", en: "..."}``.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# A string or {language: string}. Plain strings are used for every language.
LText = str | dict[str, str]

Time = Annotated[str, StringConstraints(pattern=r"^\d{2}:\d{2}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Person(_Model):
    name: str
    experience: list[str] = Field(
        default_factory=list, description="Notable previous ascents, one per entry."
    )
    contact: str | None = None
    note: LText | None = Field(None, description="Short note after the name, e.g. which peaks they climbed.")


class Peak(_Model):
    name: str
    former_name: str | None = Field(None, description="Earlier name the peak is also known by.")
    elevation_m: float
    lat: float | None = Field(None, description="Used to find the summit time in the GPX track.")
    lon: float | None = None
    date: dt.date | None = None
    time: Time | None = Field(
        None, description="Local summit time. Computed from the GPX track when lat/lon are given."
    )
    grade: str | None = Field(
        None, description="Grade of the route climbed, as the guidebook writes it, e.g. 'PD-'. Shown "
                          "with the peak in the general information and the summit times.")
    grade_system: str | None = Field(
        None, description="Grading system shown on the summit table's badge: Alpine, UIAA, ...")
    ski_grade: str | None = Field(
        None, description="Ski mountaineering grade of the route, as the guidebook writes it, e.g. '2.3 / E1'. "
                          "Shown beside the climbing grade.")
    ski_grade_system: str | None = Field(
        None, description="Ski grading system shown on its badge, e.g. Toponeige.")


class Section(_Model):
    """One technical section of a route (a peak, a ridge, a pitch group)."""

    name: str
    grade: str | None = None
    pitches: str | None = None
    leader: LText | None = None
    note: LText | None = None


class RouteGroup(_Model):
    name: str
    grade: str | None = Field(None, description="Overall grade as the guidebook writes it, e.g. 'AD+'.")
    grade_system: str | None = Field(
        None, description="Grading system shown in small caps on the badge: Alpine, UIAA, Cat., ..."
    )
    ski_grade: str | None = Field(
        None, description="Ski mountaineering grade, e.g. '2.3 / E1'; a glacier-blue badge after the grade.")
    ski_grade_system: str | None = Field(None, description="Ski grading system on its badge, e.g. Toponeige.")
    note: LText | None = Field(None, description="Extra route facts shown beside the grade, e.g. '700 m'.")
    sections: list[Section] = Field(default_factory=list)


class Accommodation(_Model):
    date: dt.date
    place: str
    kind: LText | None = Field(None, description="Hut, bivouac, tent, ...")
    altitude_m: float | None = None
    note: LText | None = None
    group: str | None = Field(
        None, description="Groups the nights table, e.g. by peak on an expedition with several climbs.")


class Camp(_Model):
    """A camp on the route, described once (the nights themselves are ``accommodation`` entries)."""

    name: str
    altitude_m: float | None = None
    lat: float | None = Field(None, description="Position, decimal degrees (shown with 6 decimals).")
    lon: float | None = None
    group: str | None = Field(None, description="The mountain or route it belongs to; one subsection per group.")
    note: LText | None = None


class Break(_Model):
    """A long daytime stop worth naming on the elevation profile, e.g. a hut."""

    date: dt.date
    place: str


class Day(_Model):
    date: dt.date
    title: LText
    text: LText = Field(description="Diary text. Blank line = new paragraph; **bold**, *italic*.")
    high_point_m: float | None = Field(
        None, description="Highest point of a day without a track, for the expedition altitude chart "
                          "(e.g. an acclimatisation walk that was not recorded).")


class BaseCamp(_Model):
    """The base camp of a high-altitude expedition. Adds the expedition altitude chart: every day from
    arrival to departure with its lowest and highest point and the altitude slept at."""

    altitude_m: float
    arrival: dt.date
    departure: dt.date

    @model_validator(mode="after")
    def _check(self) -> BaseCamp:
        if self.departure < self.arrival:
            raise ValueError("base_camp: departure is before arrival")
        return self


class TrackFile(_Model):
    """One GPX file of a trip with several. Each file gets its own route map and elevation profile,
    unless ``figures`` is false."""

    file: str = Field(description="Path relative to the trip folder.")
    name: LText | None = Field(None, description="Heading above this track's map and profile, e.g. the peak.")
    figures: bool = Field(
        True, description="False: the track counts in the tables and totals but gets no map or profile "
                          "(e.g. acclimatisation walks).")


class Photo(_Model):
    file: str = Field(description="Path relative to the trip folder.")
    caption: LText
    size: Literal["full", "half"] = Field(
        "half", description="'full' = a page of its own; 'half' = two per page."
    )


class Calibration(_Model):
    """Totals to trust over the ones computed from the GPX track.

    GPS altitude is noisy, so computed ascent is rarely exact. Give the figures you trust (a
    guidebook, or a service that corrects elevation) and every day's distance, ascent and
    descent is scaled by the same factor, so tables and rows still add up.
    """

    distance_km: float | None = None
    ascent_m: float | None = None
    descent_m: float | None = Field(
        None, description="If omitted, descent is scaled by the same factor as ascent."
    )


class MapSettings(_Model):
    basemap: Literal["plain", "tiles"] = Field(
        "plain",
        description="'tiles' puts a real map under the route: tiles are downloaded on the first build "
                    "(needs network and the `[tiles]` extra) and cached in the trip folder.",
    )
    tile_source: Literal["topo", "light"] = Field(
        "topo", description="'topo' = OpenTopoMap (contours, glaciers); 'light' = a minimal grey map."
    )
    color_by: Literal["none", "day"] = "none"
    label_peaks: bool = True


CoverStat = Literal["highest_point", "ascent", "descent", "distance", "peaks", "days", "net_time",
                    "vertical_range"]


class Cover(_Model):
    image: str = Field(description="Path relative to the trip folder.")
    kicker: LText | None = Field(None, description="Small line above the title.")


class Trip(_Model):
    schema_version: Literal[1] = 1
    languages: list[str] = Field(["lt"], description="Languages the content is written in.")
    title: LText
    subtitle: LText | None = None
    cover: Cover
    start_date: dt.date
    end_date: dt.date
    timezone: str = Field("Europe/Zurich", description="IANA zone of the track's local time.")
    day_cutoff_hour: int = Field(
        0, ge=0, le=12, description="Hour at which a track day starts (use 3 if you start at 02:30)."
    )
    region: LText
    country: LText | None = None
    kind: LText | None = Field(None, description="Climb class, e.g. 'Technical'.")
    kind_note: LText | None = Field(
        None, description="Shown in parentheses after the class in the general information table only "
                          "(not on the title page), e.g. 'unclassified ski tour'.")
    grade: str | None = Field(
        None, description="Overall grade of the whole trip as the guidebook writes grades, e.g. 'AD, III'. "
                          "Useful when the trip combines several routes: give the grade of the hardest "
                          "sections. Shown in the general information after the class.")
    participants: list[Person] = Field(default_factory=list)
    peaks: list[Peak] = Field(default_factory=list)
    route_description: LText | None = Field(
        None, description="A few paragraphs about the route itself, shown first under route information."
    )
    routes: list[RouteGroup] = Field(default_factory=list)
    tactics: LText | None = None
    gear: list[LText] = Field(default_factory=list)
    conditions: LText | None = None
    accommodation_intro: LText | None = Field(
        None, description="Text above the nights table, e.g. how the camps are named and where they are.")
    accommodation: list[Accommodation] = Field(default_factory=list)
    camps: list[Camp] = Field(
        default_factory=list,
        description="Camps on the routes, shown as one table per group (mountain) under accommodation.")
    breaks: list[Break] = Field(
        default_factory=list,
        description="Named daytime stops (1 to 5 hours) shown on the elevation profile.",
    )
    support: LText | None = None
    base_camp: BaseCamp | None = Field(
        None, description="High-altitude expeditions: the base camp. Nights without an accommodation "
                          "entry between arrival and departure are spent here. The daily table then lists "
                          "every day of the stay with where its night was spent, instead of a table of nights.")
    acclimatisation: LText | None = None
    days: list[Day] = Field(default_factory=list)
    gpx: str | list[TrackFile] = Field(
        "track.gpx",
        description="Path relative to the trip folder, or a list of files (for example one per peak of an "
                    "expedition). The statistics use all of them; each file gets its own map and profile. "
                    "Diary days outside every file's dates (travel, rest in base camp) have no track.",
    )
    map: MapSettings = Field(default_factory=MapSettings)
    photos: list[Photo] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    calibration: Calibration | None = None
    cover_stats: list[CoverStat] = Field(
        default_factory=lambda: ["highest_point", "ascent", "distance", "peaks", "days"],
        min_length=2, max_length=5,
        description="Headline numbers on the title page, in order. The first one is set in the accent colour.",
    )
    acclimatisation_chart: bool = Field(
        False, description="Add the climb-high-sleep-low chart (needs three or more days)."
    )
    show_contents: bool = True
    gpx_note: bool = Field(
        True, description="Add the standard note under the daily summary that its figures come from the "
                          "recorded GPS track and carry the usual GPS errors (the highest point in the table "
                          "need not match the highest summit).")

    def gpx_files(self) -> list[TrackFile]:
        return [TrackFile(file=self.gpx)] if isinstance(self.gpx, str) else list(self.gpx)

    @model_validator(mode="after")
    def _check(self) -> Trip:
        if isinstance(self.gpx, list) and not self.gpx:
            raise ValueError("gpx: give at least one file")
        if self.end_date < self.start_date:
            raise ValueError("end_date is before start_date")
        for p in self.peaks:
            if (p.lat is None) != (p.lon is None):
                raise ValueError(f"peak {p.name!r}: give both lat and lon, or neither")
        return self


def load_trip(trip_dir: str | Path) -> tuple[Trip, Path]:
    """Load and validate ``trip.yaml`` (or ``trip.json``) from a trip folder."""
    trip_dir = Path(trip_dir)
    for name in ("trip.yaml", "trip.yml", "trip.json"):
        path = trip_dir / name
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return Trip.model_validate(data), trip_dir
    raise FileNotFoundError(f"no trip.yaml in {trip_dir}")


def json_schema() -> dict:
    return Trip.model_json_schema()


def resolve(text: LText | None, lang: str, fallbacks: list[str] | None = None) -> str:
    """Pick the text for ``lang``; fall back through ``fallbacks`` then any available value."""
    if text is None:
        return ""
    if isinstance(text, str):
        return text
    for code in [lang, *(fallbacks or [])]:
        if code in text:
            return text[code]
    return next(iter(text.values()), "")
