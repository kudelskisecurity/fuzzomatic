#!/usr/bin/env bash

set -e

export PYTHONPATH=.
poetry run coverage run -m pytest tests/
poetry run coverage report
poetry run coverage html