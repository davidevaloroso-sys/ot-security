#!/usr/bin/env bash
set -Eeuo pipefail

REPORT_DIR="bandit-reports"


echo "[*] Preparing Python virtual environment"
python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install "bandit[toml]"

mkdir -p "${REPORT_DIR}"

echo "[*] Running Bandit full report (LOW severity / LOW confidence)"
bandit -r . \
  -r . -x .git,.venv,__pycache__,.github,k3s,tests \
  --severity-level low \
  --confidence-level low \
  -f txt \
  -o "${REPORT_DIR}/bandit-report.txt"

bandit -r . \
  -r . -x .git,.venv,__pycache__,.github,k3s,tests \
  --severity-level low \
  --confidence-level low \
  -f json \
  -o "${REPORT_DIR}/bandit-report.json"

bandit -r . \
  -r . -x .git,.venv,__pycache__,.github,k3s,tests \
  --severity-level low \
  --confidence-level low \
  -f sarif \
  -o "${REPORT_DIR}/bandit-report.sarif"

echo "[*] Enforcing Bandit gate (MEDIUM severity / MEDIUM confidence)"
bandit -r . \
  -r . -x .git,.venv,__pycache__,.github,k3s,tests \
  --severity-level medium \
  --confidence-level medium