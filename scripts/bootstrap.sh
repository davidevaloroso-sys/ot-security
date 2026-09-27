#!/usr/bin/env bash
# Run from repository root on an authorized Ubuntu/K3s administration host.
set -euo pipefail
: "${SECRET_DIR:?Set SECRET_DIR to a protected directory outside the checkout}"
: "${MQTT_CA_FILE:?Set MQTT_CA_FILE to the public issuing CA PEM}"
test -s "$MQTT_CA_FILE"
python scripts/preflight.py --cluster-only
kubectl apply -f k3s/namespace.yaml
kubectl apply -f k3s/mqtt-config.yaml
kubectl -n ot-namespace create configmap mqtt-ca --from-file=ca.crt="$MQTT_CA_FILE" --dry-run=client -o yaml | kubectl apply -f -
# Preserve existing credentials. Rotation remains an explicit operator action.
for name in mqtt-credentials mqtt-raspi-simulator mqtt-ia-consumer mqtt-nodered observability-secrets; do
  if kubectl -n ot-namespace get secret "$name" >/dev/null 2>&1; then
    printf 'Preserving existing Secret: %s\n' "$name"
  else
    test -s "$SECRET_DIR/$name.env"
    kubectl -n ot-namespace create secret generic "$name" --from-env-file="$SECRET_DIR/$name.env"
  fi
done
kubectl apply -f k3s/platform-network-policies.yaml
kubectl apply -f k3s/influxdb-deploy.yaml
kubectl -n ot-namespace rollout status deployment/influxdb --timeout=300s
printf '%s\n' 'InfluxDB ready. Provision scoped tokens, nodered-auth and grafana-influxdb, then follow README.'
