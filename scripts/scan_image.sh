#!/usr/bin/env bash
set -euo pipefail
: "${1:?Pass the exact image reference to scan}"
scan_dir="$(mktemp -d)"
trap 'rm -rf "$scan_dir"' EXIT
# Official v0.74.0 release checksum; avoid mutable transitive Actions tags.
curl --fail --silent --show-error --location https://github.com/aquasecurity/trivy/releases/download/v0.74.0/trivy_0.74.0_Linux-64bit.tar.gz -o "$scan_dir/trivy.tar.gz"
printf '%s  %s\n' 2ae6fe3ee734b7fdf11335663e18c75ea12dccc76062f09f164a3b0f8be4371a "$scan_dir/trivy.tar.gz" | sha256sum --check
tar -xzf "$scan_dir/trivy.tar.gz" -C "$scan_dir" trivy
report="${2:-scan-report.json}"
scan_status=0
"$scan_dir/trivy" image --scanners vuln,secret --severity HIGH,CRITICAL --exit-code 1 --timeout 15m --format json --output "$report" "$1" || scan_status=$?
if [ -f "$report" ]; then "$scan_dir/trivy" convert --format table "$report"; fi
if [ -n "${3:-}" ]; then
  # Also scan the signed inventory of stripped vendor binaries.
  "$scan_dir/trivy" sbom --severity HIGH,CRITICAL --exit-code 1 --format json --output "${report%.json}-sbom.json" "$3" || scan_status=1
  if [ -f "${report%.json}-sbom.json" ]; then "$scan_dir/trivy" convert --format table "${report%.json}-sbom.json"; fi
fi
exit "$scan_status"
