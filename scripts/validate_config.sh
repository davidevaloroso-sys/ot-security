#!/usr/bin/env bash
set -euo pipefail
# Fixed release archives and hashes from upstream release checksums.
tools_dir="$(mktemp -d)"
trap 'rm -rf "$tools_dir"' EXIT
curl --fail --silent --show-error --location https://github.com/rhysd/actionlint/releases/download/v1.7.7/actionlint_1.7.7_linux_amd64.tar.gz -o "$tools_dir/actionlint.tar.gz"
printf '%s  %s\n' 023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757 "$tools_dir/actionlint.tar.gz" | sha256sum --check
curl --fail --silent --show-error --location https://github.com/yannh/kubeconform/releases/download/v0.6.7/kubeconform-linux-amd64.tar.gz -o "$tools_dir/kubeconform.tar.gz"
printf '%s  %s\n' 95f14e87aa28c09d5941f11bd024c1d02fdc0303ccaa23f61cef67bc92619d73 "$tools_dir/kubeconform.tar.gz" | sha256sum --check
tar -xzf "$tools_dir/actionlint.tar.gz" -C "$tools_dir" actionlint
tar -xzf "$tools_dir/kubeconform.tar.gz" -C "$tools_dir" kubeconform
"$tools_dir/actionlint" -shellcheck= .github/workflows/cicd-k3s.yml
python scripts/render_release.py 0000000000000000000000000000000000000000 --output "$tools_dir/rendered"
python scripts/preflight.py "$tools_dir/rendered" --offline
"$tools_dir/kubeconform" -strict -summary -kubernetes-version 1.31.0 "$tools_dir/rendered/" k3s/optional/
