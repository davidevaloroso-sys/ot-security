import json
import os
import random
import time
from datetime import datetime, timezone

from pymodbus.client import ModbusTcpClient

MODBUS_HOST = os.getenv("MODBUS_HOST", "openplc")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))
DEVICE_NAME = os.getenv("DEVICE_NAME", "raspi1")

TEMP_MIN = 20.0
TEMP_MAX = 30.0
HUM_MIN = 45.0
HUM_MAX = 80.0

ALERT_CODES = {
    None: 0,
    "TEMP_BELOW_RANGE": 1,
    "TEMP_ABOVE_RANGE": 2,
    "HUM_BELOW_RANGE": 3,
    "HUM_ABOVE_RANGE": 4,
}

sequence = 0


def utc_ts():
    return int(datetime.now(timezone.utc).timestamp())


def rand_in_range(low, high, digits=1):
    return round(random.uniform(low, high), digits)


def generate_temperature():
    if random.random() < 0.10:
        if random.choice([True, False]):
            value = rand_in_range(5.0, 19.9)
            return value, False, "TEMP_BELOW_RANGE"
        value = rand_in_range(30.1, 45.0)
        return value, False, "TEMP_ABOVE_RANGE"
    value = rand_in_range(TEMP_MIN, TEMP_MAX)
    return value, True, None


def generate_humidity():
    if random.random() < 0.10:
        if random.choice([True, False]):
            value = rand_in_range(10.0, 44.9)
            return value, False, "HUM_BELOW_RANGE"
        value = rand_in_range(80.1, 95.0)
        return value, False, "HUM_ABOVE_RANGE"
    value = rand_in_range(HUM_MIN, HUM_MAX)
    return value, True, None


def build_payload():
    global sequence
    sequence += 1

    temp_value, temp_in_range, temp_alert = generate_temperature()
    hum_value, hum_in_range, hum_alert = generate_humidity()

    return {
        "device": DEVICE_NAME,
        "ts": utc_ts(),
        "sequence": sequence,
        "temperature": {
            "value": temp_value,
            "unit": "C",
            "in_range": temp_in_range,
            "alert": temp_alert,
        },
        "humidity": {
            "value": hum_value,
            "unit": "%",
            "in_range": hum_in_range,
            "alert": hum_alert,
        },
    }


def write_to_modbus(client, payload):
    temp = payload["temperature"]
    hum = payload["humidity"]

    registers = [
        int(round(temp["value"] * 10)),
        int(round(hum["value"] * 10)),
        ALERT_CODES[temp["alert"]],
        ALERT_CODES[hum["alert"]],
        payload["sequence"] % 65535,
    ]

    rr = client.write_registers(0, registers)
    if rr.isError():
        raise RuntimeError(f"write_registers failed: {rr}")

    rc0 = client.write_coil(0, temp["in_range"])
    if rc0.isError():
        raise RuntimeError(f"write_coil temp failed: {rc0}")

    rc1 = client.write_coil(1, hum["in_range"])
    if rc1.isError():
        raise RuntimeError(f"write_coil hum failed: {rc1}")


def main():
    while True:
        client = ModbusTcpClient(host=MODBUS_HOST, port=MODBUS_PORT, timeout=5)
        try:
            if not client.connect():
                raise RuntimeError(f"cannot connect to {MODBUS_HOST}:{MODBUS_PORT}")

            payload = build_payload()
            write_to_modbus(client, payload)

            print(json.dumps({
                "event": "modbus_write_ok",
                "target": f"{MODBUS_HOST}:{MODBUS_PORT}",
                "device": payload["device"],
                "sequence": payload["sequence"],
                "ts": payload["ts"],
                "temperature": payload["temperature"],
                "humidity": payload["humidity"],
            }), flush=True)

        except Exception as e:
            print(json.dumps({
                "event": "modbus_write_error",
                "target": f"{MODBUS_HOST}:{MODBUS_PORT}",
                "error": str(e),
            }), flush=True)
        finally:
            try:
                client.close()
            except Exception:
                pass

        time.sleep(PUBLISH_INTERVAL)


if __name__ == "__main__":
    main()