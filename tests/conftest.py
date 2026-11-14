from pathlib import Path

import pytest

from tripreports.sample import create_sample


@pytest.fixture(scope="session")
def sample_dir(tmp_path_factory) -> Path:
    """A fictional trip generated on the fly (no data is stored in the repository)."""
    return create_sample(tmp_path_factory.mktemp("sample") / "trip")


@pytest.fixture(scope="session")
def built(tmp_path_factory, sample_dir):
    """Build the sample once."""
    from tripreports.build import build_report

    out = tmp_path_factory.mktemp("out")
    return {"lt": build_report(sample_dir, lang="lt", out=out / "report-lt.pdf")}


@pytest.fixture
def trip_copy(tmp_path, sample_dir) -> Path:
    """A private copy of the sample trip that a test may edit."""
    import shutil

    dest = tmp_path / "trip"
    shutil.copytree(sample_dir, dest, ignore=shutil.ignore_patterns("out"))
    return dest


def edit_trip(trip_dir: Path, **changes) -> None:
    import yaml

    path = trip_dir / "trip.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.update(changes)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
