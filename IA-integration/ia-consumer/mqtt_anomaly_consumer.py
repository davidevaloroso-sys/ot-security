import json
import logging
import os
from pathlib import Path

import joblib
import pandas as pd
import paho.mqtt.client as mqtt

MODEL_PATH = Path(os.getenv("MODEL_PATH", "model_random_forest.joblib"))

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "anomaly-detector-1")

MQTT_TOPIC_TEMP = os.getenv("MQTT_TOPIC_TEMP", "lab/raspi1/temperature")
MQTT_TOPIC_HUM = os.getenv("MQTT_TOPIC_HUM", "lab/raspi1/humidity")
MQTT_ALERT_TOPIC = os.getenv("MQTT_ALERT_TOPIC", "lab/raspi1/anomaly")

ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "0.70"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

model = None


def load_model():
    global model
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Modello non trovato: {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    logging.info("Modello caricato da %s", MODEL_PATH)


def build_features(payload: dict, measure_type: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "value": float(payload["value"]),
        "tipo": measure_type,
        "unit": payload.get("unit"),
    }])


def evaluate_payload(payload: dict, topic: str) -> dict:
    measure_type = "temp" if topic == MQTT_TOPIC_TEMP else "hum"

    features = build_features(payload, measure_type)

    pred = int(model.predict(features)[0])
    score = float(model.predict_proba(features)[0][1])

    result = {
        "device": payload.get("device"),
        "topic": topic,
        "ts": payload.get("ts"),
        "value": payload.get("value"),
        "unit": payload.get("unit"),
        "sensor_alert": payload.get("alert"),
        "sensor_in_range": payload.get("in_range"),
        "model_prediction": pred,
        "model_anomaly_score": round(score, 4),
        "model_alert": score >= ANOMALY_THRESHOLD,
    }
    return result


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connesso al broker %s:%s", MQTT_BROKER, MQTT_PORT)
        client.subscribe(MQTT_TOPIC_TEMP)
        client.subscribe(MQTT_TOPIC_HUM)
        logging.info("Sottoscritto a %s e %s", MQTT_TOPIC_TEMP, MQTT_TOPIC_HUM)
    else:
        logging.error("Connessione fallita, rc=%s", rc)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        result = evaluate_payload(payload, msg.topic)

        if result["model_alert"]:
            client.publish(MQTT_ALERT_TOPIC, json.dumps(result), qos=0, retain=False)
            logging.warning("ANOMALIA RILEVATA: %s", result)
        else:
            logging.info("Payload regolare: %s", result)

    except Exception as exc:
        logging.exception("Errore durante la gestione del messaggio: %s", exc)


def main():
    if not MQTT_BROKER:
        raise RuntimeError("MQTT_BROKER environment variable is required")

    load_model()

    client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()