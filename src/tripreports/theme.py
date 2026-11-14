"""Theme loading: defaults from the package, optionally overridden by a user TOML file."""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path

ASSETS = Path(str(resources.files("tripreports") / "assets"))
FONTS_DIR = ASSETS / "fonts"
TEMPLATES_DIR = ASSETS / "templates"


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_theme(path: str | Path | None = None) -> dict:
    theme = tomllib.loads((ASSETS / "theme" / "default.toml").read_text(encoding="utf-8"))
    if path is not None:
        theme = _merge(theme, tomllib.loads(Path(path).read_text(encoding="utf-8")))
    return theme


def text_width_mm(theme: dict) -> float:
    page = theme["page"]
    return page["width_mm"] - 2 * page["margin_x_mm"]
