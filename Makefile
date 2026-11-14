PY ?= .venv/bin/python
TRIP ?= reports/sample

.PHONY: setup sample build preview test schema lint clean

setup:            ## create .venv and install the package with dev tools
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

sample:           ## write a fictional sample trip to $(TRIP) (git-ignored) to try the tool
	$(PY) -m tripreports.cli sample $(TRIP)

build:            ## build the PDF of $(TRIP) -> $(TRIP)/out/
	$(PY) -m tripreports.cli build $(TRIP) --lang lt

preview:          ## build $(TRIP) and render page images to $(TRIP)/out/preview/
	$(PY) -m tripreports.cli build $(TRIP) --lang lt --png $(TRIP)/out/preview --ppi 80

test:             ## run the test suite (generates its own sample trip; works offline)
	$(PY) -m pytest -q

schema:           ## regenerate schema/trip.schema.json from the pydantic models
	$(PY) -m tripreports.cli schema --out schema/trip.schema.json

lint:
	.venv/bin/ruff check src tests

clean:
	rm -rf $(TRIP)/out
