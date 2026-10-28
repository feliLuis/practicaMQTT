#!/usr/bin/env python3
"""Simulador del ESP32 para probar el servidor MCP SIN hardware.

Publica una distancia ficticia ~4 veces por segundo y registra los comandos
que llegan, igual que lo haría el firmware real.

Uso:
    uv run python simulate_esp32.py --prefix sis234/grupo1
"""

import argparse
import json
import logging
import random
import sys
import time
import uuid

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("simulador")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="sis234/grupoN", help="Prefijo de tópicos del grupo")
    parser.add_argument("--broker", default="broker.hivemq.com")
    parser.add_argument("--port", type=int, default=1883)
    args = parser.parse_args()

    topic_distance = f"{args.prefix}/distancia"
    topic_command = f"{args.prefix}/actuadores/cmd"

    def on_connect(client, userdata, flags, reason_code, properties):
        logger.info("Conectado (%s). Escuchando comandos en %s", reason_code, topic_command)
        client.subscribe(topic_command, qos=1)

    def on_message(client, userdata, msg):
        logger.info("COMANDO RECIBIDO: %s", msg.payload.decode("utf-8", errors="replace"))

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"sim-{uuid.uuid4().hex[:6]}")
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(1, 30)
    client.connect_async(args.broker, args.port, 60)
    client.loop_start()

    distance = 50.0
    try:
        while True:
            distance = min(200.0, max(2.0, distance + random.uniform(-3, 3)))
            client.publish(topic_distance, json.dumps({"cm": round(distance, 1)}))
            time.sleep(0.25)
    except KeyboardInterrupt:
        logger.info("Simulador detenido")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
