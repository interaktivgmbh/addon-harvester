.DEFAULT_GOAL := help

VENV := .venv
# interpreter used to create the venv — project targets Python 3.14 (override: make install PYTHON_BIN=python3)
PYTHON_BIN ?= python3.14
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip

.PHONY: help install harvest test lint build publish clean

# extra args forwarded to the harvester, e.g. make harvest ARGS="--limit 20"
# --with-github is on by default; it self-skips when no GITHUB_TOKEN/GH_TOKEN is set
ARGS ?= -v --with-github

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

$(VENV): pyproject.toml  ## (internal) create the venv and install the package + tooling
	$(PYTHON_BIN) -m venv $(VENV)
	$(PIP) install --upgrade pip build twine
	$(PIP) install -e ".[dev]"
	@touch $(VENV)

install: $(VENV)  ## Create the venv and install the package with dev extras

harvest: $(VENV)  ## Run the harvester
	$(PYTHON) main.py $(ARGS)

test: $(VENV)  ## Run the test suite
	$(PYTHON) -m pytest

lint: $(VENV)  ## Lint with ruff
	$(PYTHON) -m ruff check src tests

build: $(VENV)  ## Build sdist + wheel into dist/
	rm -rf dist
	$(PYTHON) -m build

publish: build  ## Upload dist/* to PyPI (needs credentials)
	$(PYTHON) -m twine upload dist/*

clean:  ## Remove the venv, build artifacts and caches
	rm -rf $(VENV) dist build src/*.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
