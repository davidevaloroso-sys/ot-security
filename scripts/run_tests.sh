#!/usr/bin/env bash
set -e

if [ -d "tests" ]; then
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  pip install pytest
  pytest tests
else
  echo "No tests directory, skipping tests"
fi