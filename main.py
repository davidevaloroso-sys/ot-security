"""Audit consumer: metadata logging only, no database writes."""
import logging
import os
import signal
import threading
from ot_common import SubscriptionHealth, build_mqtt_client, marker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def on_message(client, userdata, msg):
    try:
        if len(msg.payload) > 16384:
            raise ValueError("oversized payload")
        msg.payload.decode("utf-8", errors="strict")
        logging.info("MQTT received topic=%s bytes=%d qos=%d", msg.topic, len(msg.payload), msg.qos)
    except (UnicodeError, ValueError) as exc:
        logging.warning("MQTT rejected: %s", exc)


def main():
    broker = os.environ["MQTT_BROKER"]
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    marker("ready", False)
    marker("started", False)
    client = build_mqtt_client("ot-mqtt-consumer")
    health = SubscriptionHealth([os.getenv("MQTT_TOPIC", "lab/#")])
    client.on_connect = health.on_connect
    client.on_subscribe = health.on_subscribe
    client.on_disconnect = health.on_disconnect
    client.on_message = on_message
    client.connect_async(broker, int(os.getenv("MQTT_PORT", "8883")), 60)
    client.loop_start()
    marker("started", True)
    try:
        stop.wait()
    finally:
        marker("ready", False)
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
