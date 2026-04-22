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
    while not stop:
        temp = round(random.uniform(20.0, 30.0), 1)
        hum = round(random.uniform(35.0, 70.0), 1)
        now = int(time.time())
        payload_temp = json.dumps({"device": "raspi1", "value": temp, "unit": "C", "ts": now})
        payload_hum = json.dumps({"device": "raspi1", "value": hum, "unit": "%", "ts": now})

        client.publish(MQTT_TOPIC_TEMP, payload_temp, qos=0, retain=False)
        client.publish(MQTT_TOPIC_HUM, payload_hum, qos=0, retain=False)

        logging.info("Published temp=%s hum=%s", temp, hum)
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