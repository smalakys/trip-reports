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


class Peak(_Model):
    name: str
    elevation_m: float
    lat: float | None = Field(None, description="Used to find the summit time in the GPX track.")
    lon: float | None = None
    date: dt.date | None = None
    time: Time | None = Field(
        None, description="Local summit time. Computed from the GPX track when lat/lon are given."
    )


class Section(_Model):
    """One technical section of a route (a peak, a ridge, a pitch group)."""

    name: str
    grade: str | None = None
    pitches: str | None = None
    leader: LText | None = None
    note: LText | None = None


class RouteGroup(_Model):
    name: str
    grade: str | None = Field(None, description="Overall grade, e.g. 'D+, 5c, 600 m'.")
    sections: list[Section] = Field(default_factory=list)


class Accommodation(_Model):
    date: dt.date
    place: str
    kind: LText | None = Field(None, description="Hut, bivouac, tent, ...")
    altitude_m: float | None = None
    note: LText | None = None


class Day(_Model):
    date: dt.date
    title: LText
    text: LText = Field(description="Diary text. Blank line = new paragraph; **bold**, *italic*.")


class Photo(_Model):
    file: str = Field(description="Path relative to the trip folder.")
    caption: LText
    size: Literal["full", "half"] = Field(
        "half", description="'full' = a page of its own; 'half' = two per page."
    )


class Summary(_Model):
    label: LText
    text: LText


class MapSettings(_Model):
    basemap: Literal["plain", "tiles"] = Field(
        "plain", description="'tiles' downloads light map tiles (needs network and `[tiles]` extra)."
    )
    color_by: Literal["none", "day"] = "none"
    label_peaks: bool = True


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
    participants: list[Person]
    peaks: list[Peak] = Field(default_factory=list)
    summary: list[Summary] = Field(default_factory=list)
    routes: list[RouteGroup] = Field(default_factory=list)
    tactics: LText | None = None
    gear: list[LText] = Field(default_factory=list)
    conditions: LText | None = None
    accommodation: list[Accommodation] = Field(default_factory=list)
    support: LText | None = None
    acclimatisation: LText | None = None
    days: list[Day] = Field(default_factory=list)
    gpx: str = Field("track.gpx", description="Path relative to the trip folder.")
    map: MapSettings = Field(default_factory=MapSettings)
    photos: list[Photo] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    show_contents: bool = True

    @model_validator(mode="after")
    def _check(self) -> Trip:
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
