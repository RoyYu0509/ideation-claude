.PHONY: setup test smoke clean

PLUGIN_ROOT := $(shell pwd)
VENV := $(PLUGIN_ROOT)/.venv

setup:
	bash bin/setup_venv.sh

test: setup
	. $(VENV)/bin/activate && cd $(PLUGIN_ROOT) && python -m pytest -q skills/tests

# smoke is an ALIAS of test — the targets were byte-identical and no
# fixtures-based end-to-end harness exists (the old comment overstated it).
smoke: test

clean:
	rm -rf .venv .pytest_cache **/__pycache__
