.PHONY: check test lint typecheck build

PYTHON ?= python3
RUFF ?= uv run --no-sync ruff
MYPY ?= uv run --no-sync mypy

check:
	$(PYTHON) -m compileall -q src tests

lint:
	$(RUFF) check src tests

typecheck:
	$(MYPY) src tests

# Keep repository tests dependency-free while importing the src-layout package directly.
test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

build:
	uv build
