"""Shared TLS, payload contract and local health for MQTT clients."""
import math
import os
import re
import ssl
import tempfile
from pathlib import Path
import paho.mqtt.client as mqtt


def marker(name, enabled):
    directory = Path(os.getenv("HEALTH_DIR", str(Path(tempfile.gettempdir()) / "ot-health")))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / f"ot-{name}"
    if enabled:
        path.touch()
    else:
        path.unlink(missing_ok=True)


def threshold():
    value = float(os.getenv("ANOMALY_THRESHOLD", "0.70"))
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("ANOMALY_THRESHOLD must be finite and between 0 and 1")
    return value


class PayloadError(ValueError):
    pass


def validate_payload(payload, measure_type):
    if not isinstance(payload, dict):
        raise PayloadError("payload must be an object")
    expected = {"temp": "C", "hum": "%"}
    value = payload.get("value")
    try:
        finite_number = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        finite_number = False
    if not finite_number:
        raise PayloadError("value must be a finite number")
    if measure_type not in expected or payload.get("unit") != expected[measure_type]:
        raise PayloadError("unit does not match topic")
    if not isinstance(payload.get("device"), str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", payload["device"]):
        raise PayloadError("device must be 1..128 letters, digits or _.:-")
    ts = payload.get("ts")
    if isinstance(ts, bool) or not isinstance(ts, int) or not 0 <= ts <= 9223372036:
        raise PayloadError("ts must be Unix seconds within the InfluxDB range")
    if "in_range" in payload and not isinstance(payload["in_range"], bool):
        raise PayloadError("in_range must be boolean")
    alert = payload.get("alert")
    if alert is not None and (not isinstance(alert, str) or len(alert) > 128 or '\n' in alert or '\r' in alert):
        raise PayloadError("alert must be null or a single-line string up to 128 characters")
    return {"value": float(value), "tipo": measure_type, "unit": expected[measure_type]}


def build_mqtt_client(default_id, manual_ack=False):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=os.getenv("MQTT_CLIENT_ID", default_id),
                         clean_session=False, protocol=mqtt.MQTTv311,
                         manual_ack=manual_ack)
    tls = os.getenv("MQTT_TLS", "true").lower()
    if tls not in ("true", "false"):
        raise ValueError("MQTT_TLS must be true or false")
    if tls == "true":
        context = ssl.create_default_context(cafile=os.getenv("MQTT_CA_FILE"))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        cert, key = os.getenv("MQTT_CERT_FILE"), os.getenv("MQTT_KEY_FILE")
        if bool(cert) != bool(key):
            raise ValueError("Both client certificate and key are required")
        if cert:
            context.load_cert_chain(cert, key)
        client.tls_set_context(context)
    elif os.getenv("MQTT_ALLOW_INSECURE_LOCAL") != "true":
        raise ValueError("Plaintext requires explicit MQTT_ALLOW_INSECURE_LOCAL=true")
    user, password = os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD")
    if not user or not password:
        raise ValueError("MQTT_USERNAME and MQTT_PASSWORD are required")
    client.username_pw_set(user, password)
    client.reconnect_delay_set(1, 30)
    client.max_queued_messages_set(1000)
    return client


class SubscriptionHealth:
    def __init__(self, topics):
        self.topics = topics
        self.mid = None

    def on_connect(self, client, userdata, flags, reason_code, properties):
        marker("ready", False)
        if reason_code == 0:
            rc, self.mid = client.subscribe([(topic, 1) for topic in self.topics])
            if rc != mqtt.MQTT_ERR_SUCCESS:
                self.mid = None

    def on_subscribe(self, client, userdata, mid, reasons, properties):
        marker("ready", mid == self.mid and len(reasons) == len(self.topics)
               and all(r.value == 1 for r in reasons))

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        marker("ready", False)
