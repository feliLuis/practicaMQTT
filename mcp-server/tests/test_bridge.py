"""Pruebas de aws_iot_bridge.py sin red ni hardware (cliente MQTT simulado).

Ejecutar desde mcp-server/:   python -m unittest discover -s tests -v
"""

import json
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aws_iot_bridge import (  # noqa: E402
    AwsIotBridge,
    Settings,
    normalize_color,
    normalize_state,
    parse_distance,
)


class FakeReason:
    def __init__(self, failure=False):
        self.is_failure = failure


class FakeInfo:
    rc = 0


class FakeClient:
    """Sustituye a paho.mqtt.client.Client: registra lo que el puente hace."""

    def __init__(self):
        self.published = []  # (topic, payload, qos)
        self.subscribed = []
        self.on_publish_hook = None
        self.rc = 0

    def reconnect_delay_set(self, **kw):
        pass

    def connect_async(self, *a):
        self.connect_args = a

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        pass

    def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))
        if self.on_publish_hook:
            self.on_publish_hook(topic, payload)
        info = FakeInfo()
        info.rc = self.rc
        return info


def make_settings(**over):
    base = dict(
        endpoint="example-ats.iot.us-east-2.amazonaws.com", port=8883, thing_name="esp32-sis234",
        client_id="mcp-sis234", ca_path=Path("ca"), cert_path=Path("crt"), key_path=Path("key"),
        keepalive=60, topic_distance="sis234/esp32/distancia",
        topic_command="sis234/esp32/comandos", leds=("rojo", "verde", "amarillo"),
        stale_after_s=5.0, confirm_timeout_s=0.3, shadow_enabled=True, shadow_rejected=False,
    )
    base.update(over)
    return Settings(**base)


def make_bridge(**over):
    client = FakeClient()
    s = make_settings(**over)
    bridge = AwsIotBridge(s, client_factory=lambda _s: client)
    return bridge, client, s


def connect(bridge, client):
    bridge._on_connect(client, None, None, FakeReason(False), None)


def accepted(s, leds):
    return json.dumps({"state": {"reported": {"leds": leds}}, "version": 7}).encode()


class TestHelpers(unittest.TestCase):
    def test_parse_distance(self):
        self.assertEqual(parse_distance(b'{"cm":42.7}'), 42.7)
        self.assertEqual(parse_distance(b"15"), 15.0)
        self.assertIsNone(parse_distance(b"hola"))
        self.assertIsNone(parse_distance(b'{"x":1}'))
        self.assertIsNone(parse_distance(b'{"cm":"abc"}'))
        self.assertIsNone(parse_distance(b"true"))

    def test_normalize(self):
        valid = ("rojo", "verde", "amarillo")
        self.assertEqual(normalize_color("Rojo", valid), "rojo")
        self.assertEqual(normalize_color("yellow", valid), "amarillo")
        self.assertIsNone(normalize_color("azul", valid))
        self.assertEqual(normalize_state("Enciende"), "on")
        self.assertEqual(normalize_state("OFF"), "off")
        self.assertIsNone(normalize_state("quizás"))


class TestConnection(unittest.TestCase):
    def test_subscribes_on_every_connection(self):
        """Reconexión: tras caer y volver, debe re-suscribirse a los mismos tópicos."""
        bridge, client, s = make_bridge()
        connect(bridge, client)
        first = list(client.subscribed)
        self.assertIn(s.topic_distance, first)
        self.assertIn(s.topic_shadow_update_accepted, first)
        self.assertIn(s.topic_shadow_get_accepted, first)
        self.assertNotIn(s.topic_shadow_update_rejected, first)  # opcional, desactivado

        bridge._on_disconnect(client, None, None, FakeReason(), None)
        self.assertFalse(bridge.connected)
        connect(bridge, client)
        self.assertTrue(bridge.connected)
        self.assertEqual(client.subscribed, first + first)

    def test_rejected_topics_only_when_enabled(self):
        bridge, client, s = make_bridge(shadow_rejected=True)
        connect(bridge, client)
        self.assertIn(s.topic_shadow_get_rejected, client.subscribed)

    def test_shadow_disabled_does_not_subscribe_to_shadow(self):
        bridge, client, s = make_bridge(shadow_enabled=False)
        connect(bridge, client)
        self.assertEqual(client.subscribed, [s.topic_distance])

    def test_failed_connect_does_not_mark_connected(self):
        bridge, client, _ = make_bridge()
        bridge._on_connect(client, None, None, FakeReason(True), None)
        self.assertFalse(bridge.connected)
        self.assertEqual(client.subscribed, [])


class TestPublishing(unittest.TestCase):
    def test_publish_fails_when_disconnected(self):
        bridge, client, _ = make_bridge()
        ok, detail = bridge.publish_command("rojo", "on")
        self.assertFalse(ok)
        self.assertEqual(client.published, [])
        self.assertIn("conexión", detail)

    def test_publish_command_format_topic_and_qos(self):
        bridge, client, s = make_bridge()
        connect(bridge, client)
        ok, _ = bridge.publish_command("rojo", "on")
        self.assertTrue(ok)
        topic, payload, qos = client.published[0]
        self.assertEqual(topic, s.topic_command)
        self.assertEqual(json.loads(payload), {"led": "rojo", "estado": "on"})
        self.assertEqual(qos, 1)  # AWS IoT solo admite QoS 0 y 1

    def test_publish_error_code_is_reported(self):
        bridge, client, _ = make_bridge()
        connect(bridge, client)
        client.rc = 4
        ok, detail = bridge.publish_command("rojo", "on")
        self.assertFalse(ok)
        self.assertIn("4", detail)


class TestIncomingMessages(unittest.TestCase):
    def test_distance_stored(self):
        bridge, client, s = make_bridge()
        self.assertEqual(bridge.last_distance(), (None, None))
        bridge.handle_message(s.topic_distance, b'{"cm":42.7}')
        reading, age = bridge.last_distance()
        self.assertEqual(reading.cm, 42.7)
        self.assertGreaterEqual(age, 0)

    def test_invalid_distance_keeps_previous_value(self):
        bridge, _, s = make_bridge()
        bridge.handle_message(s.topic_distance, b'{"cm":10}')
        bridge.handle_message(s.topic_distance, b"basura")
        self.assertEqual(bridge.last_distance()[0].cm, 10.0)

    def test_update_accepted_records_reported_leds(self):
        bridge, _, s = make_bridge()
        bridge.handle_message(s.topic_shadow_update_accepted, accepted(s, {"rojo": "on"}))
        self.assertEqual(bridge.led_reports()["rojo"][0], "on")

    def test_malformed_shadow_json_is_ignored(self):
        bridge, _, s = make_bridge()
        bridge.handle_message(s.topic_shadow_update_accepted, b"{no es json")
        self.assertEqual(bridge.led_reports(), {})


class TestCommandConfirmation(unittest.TestCase):
    def test_confirmed_when_device_reports(self):
        bridge, client, s = make_bridge()
        connect(bridge, client)

        def device(topic, payload):  # el ESP32 simulado confirma por el Shadow
            if topic == s.topic_command:
                cmd = json.loads(payload)
                threading.Timer(0.05, bridge.handle_message, (
                    s.topic_shadow_update_accepted, accepted(s, {cmd["led"]: cmd["estado"]}))).start()

        client.on_publish_hook = device
        res = bridge.send_led_commands([("rojo", "on")], timeout_s=1.0)
        self.assertTrue(res[0].sent)
        self.assertTrue(res[0].confirmed)

    def test_sent_but_not_confirmed_on_timeout(self):
        bridge, client, _ = make_bridge()
        connect(bridge, client)
        res = bridge.send_led_commands([("rojo", "on")], timeout_s=0.1)
        self.assertTrue(res[0].sent)
        self.assertFalse(res[0].confirmed)  # MQTT aceptó, pero nadie confirmó

    def test_old_report_does_not_confirm_new_command(self):
        """Un 'on' reportado ANTES de enviar no puede confirmar un comando nuevo."""
        bridge, client, s = make_bridge()
        connect(bridge, client)
        bridge.handle_message(s.topic_shadow_update_accepted, accepted(s, {"rojo": "on"}))
        res = bridge.send_led_commands([("rojo", "on")], timeout_s=0.1)
        self.assertFalse(res[0].confirmed)

    def test_wrong_state_report_does_not_confirm(self):
        bridge, client, s = make_bridge()
        connect(bridge, client)

        def device(topic, payload):
            if topic == s.topic_command:
                threading.Timer(0.02, bridge.handle_message,
                                (s.topic_shadow_update_accepted, accepted(s, {"rojo": "off"}))).start()

        client.on_publish_hook = device
        res = bridge.send_led_commands([("rojo", "on")], timeout_s=0.2)
        self.assertFalse(res[0].confirmed)

    def test_not_sent_when_disconnected(self):
        bridge, client, _ = make_bridge()
        res = bridge.send_led_commands([("rojo", "on")], timeout_s=0.1)
        self.assertFalse(res[0].sent)
        self.assertFalse(res[0].confirmed)

    def test_multiple_leds_confirmed_individually(self):
        bridge, client, s = make_bridge()
        connect(bridge, client)

        def device(topic, payload):
            if topic == s.topic_command:
                cmd = json.loads(payload)
                if cmd["led"] != "verde":  # el verde nunca responde
                    threading.Timer(0.02, bridge.handle_message, (
                        s.topic_shadow_update_accepted, accepted(s, {cmd["led"]: cmd["estado"]}))).start()

        client.on_publish_hook = device
        res = bridge.send_led_commands([("rojo", "on"), ("verde", "off"), ("amarillo", "off")], 0.4)
        by = {r.color: r for r in res}
        self.assertTrue(by["rojo"].confirmed)
        self.assertTrue(by["amarillo"].confirmed)
        self.assertFalse(by["verde"].confirmed)
        self.assertEqual([r.color for r in res], ["rojo", "verde", "amarillo"])  # orden conservado


class TestShadow(unittest.TestCase):
    def get_accepted_payload(self):
        return json.dumps({"state": {"desired": {"leds": {"rojo": "on"}},
                                     "reported": {"leds": {"rojo": "off"}},
                                     "delta": {"leds": {"rojo": "on"}}},
                           "version": 12}).encode()

    def test_request_shadow_success(self):
        bridge, client, s = make_bridge()
        connect(bridge, client)

        def aws(topic, payload):
            if topic == s.topic_shadow_get:
                threading.Timer(0.03, bridge.handle_message,
                                (s.topic_shadow_get_accepted, self.get_accepted_payload())).start()

        client.on_publish_hook = aws
        snap, err = bridge.request_shadow(timeout_s=1.0)
        self.assertEqual(err, "")
        self.assertEqual(snap.version, 12)
        self.assertEqual(snap.desired, {"rojo": "on"})
        self.assertEqual(snap.reported, {"rojo": "off"})
        self.assertEqual(snap.delta, {"rojo": "on"})
        self.assertEqual(client.published[0][0], s.topic_shadow_get)

    def test_request_shadow_timeout(self):
        bridge, client, _ = make_bridge()
        connect(bridge, client)
        snap, err = bridge.request_shadow(timeout_s=0.1)
        self.assertIsNone(snap)
        self.assertIn("no respondió", err)

    def test_request_shadow_rejected(self):
        bridge, client, s = make_bridge(shadow_rejected=True)
        connect(bridge, client)

        def aws(topic, payload):
            if topic == s.topic_shadow_get:
                threading.Timer(0.02, bridge.handle_message, (
                    s.topic_shadow_get_rejected, b'{"code":404,"message":"No shadow exists"}')).start()

        client.on_publish_hook = aws
        snap, err = bridge.request_shadow(timeout_s=1.0)
        self.assertIsNone(snap)
        self.assertIn("rechazó", err)

    def test_request_shadow_when_disabled(self):
        bridge, _, _ = make_bridge(shadow_enabled=False)
        snap, err = bridge.request_shadow()
        self.assertIsNone(snap)
        self.assertIn("deshabilitado", err)


class TestSettings(unittest.TestCase):
    def test_problems_lists_missing_files_and_endpoint(self):
        s = make_settings(endpoint="")
        problems = s.problems()
        self.assertEqual(len(problems), 4)  # endpoint + 3 archivos inexistentes

    def test_shadow_topics_use_thing_name(self):
        s = make_settings()
        self.assertEqual(s.topic_shadow_get, "$aws/things/esp32-sis234/shadow/get")
        self.assertEqual(s.topic_shadow_update_accepted,
                         "$aws/things/esp32-sis234/shadow/update/accepted")


if __name__ == "__main__":
    unittest.main()
