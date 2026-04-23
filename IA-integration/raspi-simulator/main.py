import os
import json
import time
import random
import logging
import signal
import sys
import paho.mqtt.client as mqtt

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "raspi-simulator-1")
MQTT_TOPIC_TEMP = os.getenv("MQTT_TOPIC_TEMP", "lab/raspi1/temperature")
MQTT_TOPIC_HUM = os.getenv("MQTT_TOPIC_HUM", "lab/raspi1/humidity")
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
stop = False

def handle_signal(signum, frame):
    global stop
    logging.info("Received signal %s, shutting down...", signum)
    stop = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT broker %s:%s", MQTT_BROKER, MQTT_PORT)
    else:
        logging.error("Failed to connect, rc=%s", rc)

def build_client():
    if not MQTT_BROKER:
        raise RuntimeError("MQTT_BROKER environment variable is required")
    client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    return client

def publish_loop(client):
    """
    Simulatore di sensore:
    - Range normale:
        temp: 20.0 - 30.0 °C
        hum:  45.0 - 80.0 %
    - Ogni tanto genera valori fuori range per testare gli alert.
    - Aggiunge sempre il campo 'alert' nel payload (None se in range).
    """
    normal_temp_min = 20.0
    normal_temp_max = 30.0
    normal_hum_min = 45.0
    normal_hum_max = 80.0

    global stop
    while not stop:
        # Valori "normali"
        temp = round(random.uniform(normal_temp_min, normal_temp_max), 1)
        hum = round(random.uniform(normal_hum_min, normal_hum_max), 1)

        # Ogni tanto genera anomalie
        anomaly_chance = random.random()

        # 5% delle volte, temperatura fuori range
        if anomaly_chance < 0.05:
            # 50% troppo bassa, 50% troppo alta
            if random.random() < 0.5:
                temp = round(random.uniform(0.0, normal_temp_min - 5.0), 1)
            else:
                temp = round(random.uniform(normal_temp_max + 5.0, 90.0), 1)

        # Altre 5% delle volte, umidità fuori range
        elif anomaly_chance < 0.10:
            if random.random() < 0.5:
                hum = round(random.uniform(0.0, normal_hum_min - 10.0), 1)
            else:
                hum = round(random.uniform(normal_hum_max + 5.0, 100.0), 1)

        now = int(time.time())

        # Determina se i valori sono in range
        temp_in_range = normal_temp_min <= temp <= normal_temp_max
        hum_in_range = normal_hum_min <= hum <= normal_hum_max

        # Messaggi di alert locali
        temp_alert = None
        hum_alert = None

        if not temp_in_range:
            if temp < normal_temp_min:
                temp_alert = "TEMP_BELOW_RANGE"
            else:
                temp_alert = "TEMP_ABOVE_RANGE"

        if not hum_in_range:
            if hum < normal_hum_min:
                hum_alert = "HUM_BELOW_RANGE"
            else:
                hum_alert = "HUM_ABOVE_RANGE"

        payload_temp = {
            "device": "raspi1",
            "value": temp,
            "unit": "C",
            "ts": now,
            "in_range": temp_in_range,
            "alert": temp_alert,
        }

        payload_hum = {
            "device": "raspi1",
            "value": hum,
            "unit": "%",
            "ts": now,
            "in_range": hum_in_range,
            "alert": hum_alert,
        }

        client.publish(MQTT_TOPIC_TEMP, json.dumps(payload_temp), qos=0, retain=False)
        client.publish(MQTT_TOPIC_HUM, json.dumps(payload_hum), qos=0, retain=False)

        logging.info(
            "Published temp=%s hum=%s (anomaly_chance=%.3f, temp_in_range=%s, hum_in_range=%s, temp_alert=%s, hum_alert=%s)",
            temp,
            hum,
            anomaly_chance,
            temp_in_range,
            hum_in_range,
            temp_alert,
            hum_alert,
        )

        time.sleep(PUBLISH_INTERVAL)

def main():
    client = build_client()
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()
    try:
        publish_loop(client)
    finally:
        client.loop_stop()
        client.disconnect()
        logging.info("Simulator stopped")
        sys.exit(0)

if __name__ == "__main__":
    main()