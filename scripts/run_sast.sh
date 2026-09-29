#!/usr/bin/env bash
set -Eeuo pipefail

REPORT_DIR="bandit-reports"
EXCLUDES=".git,.venv,__pycache__,.github,k3s,tests"
TARGETS=(
  "main.py"
  "ot_common.py"
  "IA-integration/ia-consumer"
  "IA-integration/raspi-simulator"
  "scripts/preflight.py"
  "scripts/initialize_influx.py"
  "scripts/provision_influx_tokens.py"
  "scripts/postdeploy_check.py"
)

mkdir -p "${REPORT_DIR}"

echo "[*] Running Bandit TXT report (non-blocking report generation)"
bandit -r "${TARGETS[@]}" \
  -x "${EXCLUDES}" \
  --severity-level low \
  --confidence-level low \
  --exit-zero \
  -f txt \
  -o "${REPORT_DIR}/bandit-report.txt"

echo "[*] Running Bandit JSON report (non-blocking report generation)"
bandit -r "${TARGETS[@]}" \
  -x "${EXCLUDES}" \
  --severity-level low \
  --confidence-level low \
  --exit-zero \
  -f json \
  -o "${REPORT_DIR}/bandit-report.json"

echo "[*] Running Bandit gate (blocking on Medium+ / Medium+)"
bandit -r "${TARGETS[@]}" \
  -x "${EXCLUDES}" \
  --severity-level medium \
  --confidence-level medium
