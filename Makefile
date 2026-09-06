.PHONY: check test

PYTHON ?= python3

check:
	$(PYTHON) -m compileall -q src tests

# Keep repository tests dependency-free while importing the src-layout package directly.
test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
