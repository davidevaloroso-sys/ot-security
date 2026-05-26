#!/usr/bin/env bash
set -Eeuo pipefail

REPORT_DIR="bandit-reports"
CONFIG_FILE=".bandit"

echo "[*] Preparing Python virtual environment"
python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install "bandit[toml]"

mkdir -p "${REPORT_DIR}"

echo "[*] Running Bandit full report (LOW severity / LOW confidence)"
bandit -r . \
  -c "${CONFIG_FILE}" \
  --severity-level low \
  --confidence-level low \
  -f txt \
  -o "${REPORT_DIR}/bandit-report.txt"

bandit -r . \
  -c "${CONFIG_FILE}" \
  --severity-level low \
  --confidence-level low \
  -f json \
  -o "${REPORT_DIR}/bandit-report.json"

bandit -r . \
  -c "${CONFIG_FILE}" \
  --severity-level low \
  --confidence-level low \
  -f sarif \
  -o "${REPORT_DIR}/bandit-report.sarif"

echo "[*] Enforcing Bandit gate (MEDIUM severity / MEDIUM confidence)"
bandit -r . \
  -c "${CONFIG_FILE}" \
  --severity-level medium \
  --confidence-level medium