import json
import logging
import os
import random
import signal
import sys
import threading
import time

import paho.mqtt.client as mqtt

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "raspi-simulator-1")
MQTT_TOPIC_TEMP = os.getenv("MQTT_TOPIC_TEMP", "lab/raspi1/temperature")
MQTT_TOPIC_HUM = os.getenv("MQTT_TOPIC_HUM", "lab/raspi1/humidity")
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))
MQTT_CONNECT_TIMEOUT = int(os.getenv("MQTT_CONNECT_TIMEOUT", "20"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("raspi-simulator")

stop = False
connected = threading.Event()


def handle_signal(signum, frame):
    global stop
    logger.info("Received signal %s, shutting down", signum)
    stop = True
    connected.set()


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        connected.set()
        logger.info(
            "MQTT connected broker=%s:%s client_id=%s",
            MQTT_BROKER,
            MQTT_PORT,
            MQTT_CLIENT_ID,
        )
    else:
        connected.clear()
        logger.error("MQTT connection refused rc=%s", rc)


def on_connect_fail(client, userdata):
    connected.clear()
    logger.error(
        "MQTT TCP connection failed broker=%s:%s",
        MQTT_BROKER,
        MQTT_PORT,
    )


def on_disconnect(client, userdata, rc, properties=None):
    connected.clear()
    if rc == 0:
        logger.info("MQTT disconnected cleanly")
    else:
        logger.warning("MQTT disconnected unexpectedly rc=%s; retrying", rc)


def build_client():
    if not MQTT_BROKER:
        raise RuntimeError("MQTT_BROKER environment variable is required")

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION1,
        client_id=MQTT_CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_connect_fail = on_connect_fail
    client.on_disconnect = on_disconnect
    client.enable_logger(logger)
    return client


def publish_json(client, topic, payload):
    message = client.publish(
        topic,
        json.dumps(payload),
        qos=1,
        retain=False,
    )

    if message.rc != mqtt.MQTT_ERR_SUCCESS:
        logger.error(
            "MQTT publish enqueue failed topic=%s rc=%s",
            topic,
            message.rc,
        )
        return False

    message.wait_for_publish(timeout=5)

    if not message.is_published():
        logger.error("MQTT publish timeout topic=%s", topic)
        return False

    logger.info("MQTT published topic=%s payload=%s", topic, payload)
    return True


def publish_loop(client):
    normal_temp_min, normal_temp_max = 20.0, 30.0
    normal_hum_min, normal_hum_max = 45.0, 80.0

    global stop

    while not stop:
        if not connected.wait(timeout=MQTT_CONNECT_TIMEOUT):
            logger.warning(
                "MQTT unavailable; waiting broker=%s:%s",
                MQTT_BROKER,
                MQTT_PORT,
            )
            continue

        temp = round(random.uniform(normal_temp_min, normal_temp_max), 1)
        hum = round(random.uniform(normal_hum_min, normal_hum_max), 1)
        anomaly_chance = random.random()

        if anomaly_chance < 0.05:
            temp = (
                round(random.uniform(0.0, normal_temp_min - 5.0), 1)
                if random.random() < 0.5
                else round(random.uniform(normal_temp_max + 5.0, 90.0), 1)
            )
        elif anomaly_chance < 0.10:
            hum = (
                round(random.uniform(0.0, normal_hum_min - 10.0), 1)
                if random.random() < 0.5
                else round(random.uniform(normal_hum_max + 5.0, 100.0), 1)
            )

        temp_in_range = normal_temp_min <= temp <= normal_temp_max
        hum_in_range = normal_hum_min <= hum <= normal_hum_max

        temp_alert = (
            None if temp_in_range
            else "TEMP_BELOW_RANGE" if temp < normal_temp_min
            else "TEMP_ABOVE_RANGE"
        )
        hum_alert = (
            None if hum_in_range
            else "HUM_BELOW_RANGE" if hum < normal_hum_min
            else "HUM_ABOVE_RANGE"
        )

        timestamp = int(time.time())

        payload_temp = {
            "device": "raspi1",
            "value": temp,
            "unit": "C",
            "ts": timestamp,
            "in_range": temp_in_range,
            "alert": temp_alert,
        }
        payload_hum = {
            "device": "raspi1",
            "value": hum,
            "unit": "%",
            "ts": timestamp,
            "in_range": hum_in_range,
            "alert": hum_alert,
        }

        temp_ok = publish_json(client, MQTT_TOPIC_TEMP, payload_temp)
        hum_ok = publish_json(client, MQTT_TOPIC_HUM, payload_hum)

        logger.info(
            "Cycle completed temp_ok=%s hum_ok=%s temp=%s hum=%s anomaly_chance=%.3f",
            temp_ok,
            hum_ok,
            temp,
            hum,
            anomaly_chance,
        )

        for _ in range(PUBLISH_INTERVAL):
            if stop:
                break
            time.sleep(1)


def main():
    client = build_client()

    logger.info(
        "MQTT connection starting broker=%s:%s temp_topic=%s hum_topic=%s",
        MQTT_BROKER,
        MQTT_PORT,
        MQTT_TOPIC_TEMP,
        MQTT_TOPIC_HUM,
    )

    client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()

    try:
        publish_loop(client)
    finally:
        client.loop_stop()
        client.disconnect()
        logger.info("Simulator stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()