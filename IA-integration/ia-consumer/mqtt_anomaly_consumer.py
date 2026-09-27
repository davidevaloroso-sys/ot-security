"""Validated inference with bounded worker queue and explicit QoS 1 acknowledgments."""
import hashlib
import json
import logging
import os
import queue
import signal
import threading
from importlib.metadata import version
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import paho.mqtt.client as mqtt
from ot_common import SubscriptionHealth, build_mqtt_client, marker, threshold, validate_payload, PayloadError

MODEL_PATH = Path(os.getenv("MODEL_PATH", "model_random_forest.joblib"))
MQTT_TOPIC_TEMP = os.getenv("MQTT_TOPIC_TEMP", "lab/raspi1/temperature")
MQTT_TOPIC_HUM = os.getenv("MQTT_TOPIC_HUM", "lab/raspi1/humidity")
MQTT_ALERT_TOPIC = os.getenv("MQTT_ALERT_TOPIC", "lab/raspi1/anomaly")
ANOMALY_THRESHOLD = threshold()
model = None
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def anomaly_index(estimator):
    classes = list(estimator.classes_)
    if len(classes) != 2 or set(classes) != {0, 1}:
        raise ValueError("Model classes must be exactly 0 and 1")
    return classes.index(1)


def load_model():
    global model
    metadata = json.loads(MODEL_PATH.with_name("training_metrics.json").read_text())
    if metadata["threshold"] != ANOMALY_THRESHOLD:
        raise ValueError("Runtime threshold differs from evaluated threshold; retrain/re-evaluate")
    for package, expected in metadata["dependencies"].items():
        if version(package) != expected:
            raise ValueError(f"Model dependency mismatch: {package}")
    if hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() != metadata["model_sha256"]:
        raise ValueError("Model hash mismatch")
    # Only load trusted build artifacts. Joblib deserialization is not a sandbox.
    model = joblib.load(MODEL_PATH)
    anomaly_index(model)
    evaluate_payload({"device": "startup", "ts": 0, "value": 25, "unit": "C"}, MQTT_TOPIC_TEMP)
    evaluate_payload({"device": "startup", "ts": 0, "value": 50, "unit": "%"}, MQTT_TOPIC_HUM)


def build_features(payload, measure_type):
    return pd.DataFrame([validate_payload(payload, measure_type)])


def evaluate_payload(payload, topic):
    measure_type = {MQTT_TOPIC_TEMP: "temp", MQTT_TOPIC_HUM: "hum"}.get(topic)
    features = build_features(payload, measure_type)
    index = anomaly_index(model)
    probabilities = np.asarray(model.predict_proba(features)[0])
    if probabilities.shape != (2,) or not np.isfinite(probabilities).all() or (probabilities < 0).any() or (probabilities > 1).any() or not np.isclose(probabilities.sum(), 1):
        raise ValueError("Invalid model probabilities")
    score = float(probabilities[index])
    result = dict(payload)
    result.update(topic=topic, model_prediction=int(model.classes_[int(np.argmax(probabilities))]),
                  model_anomaly_score=score, model_alert=score >= ANOMALY_THRESHOLD)
    canonical = json.dumps({"topic": topic, "payload": payload}, sort_keys=True, separators=(",", ":"), allow_nan=False)
    result["event_id"] = hashlib.sha256(canonical.encode()).hexdigest()
    return result


class Processor:
    def __init__(self, client):
        self.client = client
        self.messages = queue.Queue(maxsize=256)
        self.stop = threading.Event()
        self.failed = threading.Event()

    def on_message(self, client, userdata, msg):
        # Never wait for PUBACK on Paho's network thread.
        try:
            if len(msg.payload) > 16384:
                logging.warning("Rejected MQTT payload: exceeds 16384 bytes")
                self.ack(msg)
                return
            self.messages.put_nowait(msg)
        except queue.Full:
            logging.error("Inference queue full; input not acknowledged; restart required")
            self.failed.set()
            marker("ready", False)
        except Exception:
            logging.exception("Input callback failed")
            self.failed.set()
            marker("ready", False)

    def ack(self, msg):
        if msg.qos and self.client.ack(msg.mid, msg.qos) != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("Input acknowledgment failed")

    def process(self, msg):
        def reject_constant(value):
            raise ValueError("Non-standard JSON numeric constant")

        try:
            payload = json.loads(msg.payload.decode("utf-8"), parse_constant=reject_constant)
        except (ValueError, UnicodeError, RecursionError):
            logging.warning("Rejected malformed JSON topic=%s", msg.topic)
            self.ack(msg)
            return
        try:
            result = evaluate_payload(payload, msg.topic)
        except PayloadError:
            logging.warning("Rejected MQTT payload topic=%s", msg.topic)
            self.ack(msg)  # Poison messages are deliberately discarded, with an explicit log.
            return
        if result["model_alert"]:
            info = self.client.publish(MQTT_ALERT_TOPIC, json.dumps(result, allow_nan=False), qos=1, retain=False)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"Alert enqueue failed: {info.rc}")
            while not self.stop.is_set():
                info.wait_for_publish(timeout=1)
                if info.is_published():
                    break
            else:
                return  # Input remains unacknowledged on shutdown.
            logging.warning("Alert confirmed by broker event_id=%s", result["event_id"])
        self.ack(msg)

    def run(self):
        while not self.stop.is_set():
            try:
                msg = self.messages.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self.process(msg)
            except Exception:
                logging.exception("Processing failed; input not acknowledged")
                self.failed.set()
                marker("ready", False)
                return
            finally:
                self.messages.task_done()


def main():
    marker("ready", False)
    marker("started", False)
    load_model()
    client = build_mqtt_client("ia-consumer-1", manual_ack=True)
    processor = Processor(client)
    health = SubscriptionHealth([MQTT_TOPIC_TEMP, MQTT_TOPIC_HUM])
    client.on_connect = health.on_connect
    client.on_subscribe = health.on_subscribe
    client.on_disconnect = health.on_disconnect
    client.on_message = processor.on_message
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: processor.stop.set())
    worker = threading.Thread(target=processor.run, name="inference", daemon=True)
    worker.start()
    client.connect_async(os.environ["MQTT_BROKER"], int(os.getenv("MQTT_PORT", "8883")), 60)
    client.loop_start()
    marker("started", True)
    try:
        while not processor.stop.wait(0.5):
            if processor.failed.is_set():
                raise RuntimeError("Inference worker failed")
    finally:
        processor.stop.set()
        worker.join(timeout=5)
        marker("ready", False)
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
