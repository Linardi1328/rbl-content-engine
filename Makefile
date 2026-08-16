.PHONY: check test

PYTHON ?= python3

check:
	$(PYTHON) -m compileall -q src tests

# Phase 0 implementation should keep this command dependency-free.
test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
