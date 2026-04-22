import os
import time
import logging
import signal
import sys

import paho.mqtt.client as mqtt

MQTT_BROKER = os.getenv("MQTT_BROKER")
if not MQTT_BROKER:
    raise RuntimeError("MQTT_BROKER environment variable is required")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensors/#")
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "ot-mqtt-consumer")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

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
        client.subscribe(MQTT_TOPIC)
        logging.info("Subscribed to %s", MQTT_TOPIC)
    else:
        logging.error("Failed to connect, rc=%s", rc)


def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors="ignore")
    logging.info("Message on %s: %s", msg.topic, payload)
    # Qui più avanti metterai la logica applicativa (parse JSON, scrivi su DB, ecc.)


def build_client() -> mqtt.Client:
    client = mqtt.Client(client_id=CLIENT_ID)
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    return client


def main():
    client = build_client()

    while not stop:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_start()

            while not stop:
                time.sleep(1)

            break
        except Exception as exc:
            logging.exception("MQTT error: %s", exc)
            time.sleep(5)

    client.loop_stop()
    client.disconnect()
    logging.info("MQTT consumer stopped")
    sys.exit(0)


if __name__ == "__main__":
    main()