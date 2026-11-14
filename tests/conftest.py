from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "synthetic-traverse"


@pytest.fixture(scope="session")
def example_dir() -> Path:
    return EXAMPLE


@pytest.fixture(scope="session")
def built(tmp_path_factory, example_dir):
    """Build the example once in each language."""
    from tripreports.build import build_report

    out = tmp_path_factory.mktemp("out")
    return {lang: build_report(example_dir, lang=lang, out=out / f"report-{lang}.pdf")
            for lang in ("lt", "en")}
