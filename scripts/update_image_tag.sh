#!/usr/bin/env bash
set -e

IMAGE_FULL="$1"  # es: ghcr.io/davidevaloroso-sys/ot-security:abcdef1234
FILE="k3s/ot-consumer-deploy.yaml"

yq -i ".spec.template.spec.containers[0].image = \"$IMAGE_FULL\"" "$FILE"