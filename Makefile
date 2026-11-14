PY ?= .venv/bin/python
EXAMPLE = examples/synthetic-traverse

.PHONY: setup example preview test schema data lint clean update-preview

setup:            ## create .venv and install the package with dev tools
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

example:          ## build the synthetic example in Lithuanian and English -> $(EXAMPLE)/out/
	$(PY) -m tripreports.cli build $(EXAMPLE) --lang lt --lang en

preview:          ## build the example and render page images to $(EXAMPLE)/out/preview/
	$(PY) -m tripreports.cli build $(EXAMPLE) --lang lt --lang en --png $(EXAMPLE)/out/preview --ppi 80

test:             ## run the test suite (includes a full build of the example)
	$(PY) -m pytest -q

schema:           ## regenerate schema/trip.schema.json from the pydantic models
	$(PY) -m tripreports.cli schema --out schema/trip.schema.json

data:             ## regenerate the synthetic GPX track and photos
	$(PY) $(EXAMPLE)/generate.py

lint:
	.venv/bin/ruff check src tests examples

clean:
	rm -rf $(EXAMPLE)/out

update-preview:   ## refresh the committed example previews (only when the look changed on purpose)
	$(PY) -m tripreports.cli build $(EXAMPLE) --lang lt --lang en --png $(EXAMPLE)/out/preview --ppi 80
	mkdir -p $(EXAMPLE)/preview && rm -f $(EXAMPLE)/preview/*.png
	for p in 01 04 07 08 11; do cp $(EXAMPLE)/out/preview/page-en-$$p.png $(EXAMPLE)/preview/en-$$p.png; done
