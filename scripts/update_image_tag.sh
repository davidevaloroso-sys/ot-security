#!/usr/bin/env bash
set -euo pipefail

NEW_IMAGE="$1"
FILE="k3s/ot-consumer-deploy.yaml"

yq -i "
  (select(.kind == \"Deployment\")
    | .spec.template.spec.containers[0].image) = \"${NEW_IMAGE}\"
" "$FILE"