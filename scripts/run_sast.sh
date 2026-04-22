#!/usr/bin/env bash
set -e

python -m venv .venv
source .venv/bin/activate
pip install bandit -r requirements.txt

# Se vuoi essere soft all'inizio:
bandit -r . -ll || echo "Bandit found issues, but not failing pipeline yet"