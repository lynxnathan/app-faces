#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv run --frozen ruff check app_faces tests install.py
uv run --frozen ruff format --check app_faces tests install.py
uv run --frozen mypy
uv run --frozen pytest -q
