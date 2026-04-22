#!/usr/bin/env bash
set -euo pipefail

NEW_IMAGE="$1"

FILE="k3s/ot-consumer-deploy.yaml"

# Aggiorna SOLO il Deployment:
# .spec.template.spec.containers[0].image del primo documento (Deployment)
# Il Service (secondo documento) resta intatto.
yq -i '
  (select(.kind == "Deployment")
    | .spec.template.spec.containers[0].image) = strenv(NEW_IMAGE)
' "$FILE"