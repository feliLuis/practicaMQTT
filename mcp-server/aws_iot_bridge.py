"""Puente MQTT/TLS hacia AWS IoT Core para el servidor MCP (SIS-234).

Este módulo contiene TODA la lógica de comunicación y es importable y
comprobable sin hardware ni red (el cliente MQTT se inyecta mediante
``client_factory``).

Conceptos clave
---------------
* **Comando enviado** != **estado confirmado.**  Publicar en MQTT solo prueba que
  AWS aceptó el mensaje. El ESP32 confirma tras aplicar el comando publicando su
  estado en el Device Shadow (``shadow/update/accepted``). ``send_led_commands``
  distingue ambos casos.
* La identidad MQTT del servidor es INDEPENDIENTE de la del ESP32: su propio
  certificado, clave, Client ID (``mcp-sis234``) y política.
* Nunca se usa ``print()``: el transporte MCP stdio usa stdout; se registra con
  ``logging`` (stderr).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger("smart-object.bridge")


# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
def load_dotenv(path: Path) -> None:
    """Carga CLAVE=valor de un .env sin pisar variables ya definidas."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "si", "sí"}


@dataclass(frozen=True)
class Settings:
    """Parámetros del servidor. Los tópicos deben coincidir con la política AWS."""

    endpoint: str
    port: int
    thing_name: str
    client_id: str
    ca_path: Path
    cert_path: Path
    key_path: Path
    keepalive: int
    topic_distance: str
    topic_command: str
    leds: tuple[str, ...]
    stale_after_s: float
    confirm_timeout_s: float
    shadow_enabled: bool
    shadow_rejected: bool

    @classmethod
    def from_env(cls, base_dir: Path | None = None) -> "Settings":
        base = base_dir or Path(__file__).resolve().parent
        load_dotenv(base / ".env")

        def path(name: str, default: str) -> Path:
            p = Path(os.environ.get(name, default)).expanduser()
            return p if p.is_absolute() else base / p

        return cls(
            endpoint=os.environ.get("AWS_IOT_ENDPOINT", "").strip(),
            port=int(os.environ.get("AWS_IOT_PORT", "8883")),
            thing_name=os.environ.get("AWS_THING_NAME", "esp32-sis234"),
            client_id=os.environ.get("MQTT_CLIENT_ID", "mcp-sis234"),
            ca_path=path("AWS_CA_PATH", "certs/AmazonRootCA1.pem"),
            cert_path=path("AWS_CERT_PATH", "certs/mcp-certificate.pem.crt"),
            key_path=path("AWS_KEY_PATH", "certs/mcp-private.pem.key"),
            keepalive=int(os.environ.get("MQTT_KEEPALIVE", "60")),
            topic_distance=os.environ.get("TOPIC_DISTANCE", "sis234/esp32/distancia"),
            topic_command=os.environ.get("TOPIC_COMMAND", "sis234/esp32/comandos"),
            leds=tuple(
                c.strip().lower()
                for c in os.environ.get("LED_COLORS", "rojo,verde,amarillo").split(",")
                if c.strip()
            ),
            stale_after_s=float(os.environ.get("STALE_AFTER_S", "5")),
            confirm_timeout_s=float(os.environ.get("CONFIRM_TIMEOUT_S", "3")),
            shadow_enabled=_env_bool("SHADOW_ENABLED", True),
            shadow_rejected=_env_bool("SHADOW_SUBSCRIBE_REJECTED", False),
        )

    # -- tópicos del Device Shadow clásico (sin nombre) ---------------------- #
    @property
    def shadow_base(self) -> str:
        return f"$aws/things/{self.thing_name}/shadow"

    @property
    def topic_shadow_get(self) -> str:
        return f"{self.shadow_base}/get"

    @property
    def topic_shadow_get_accepted(self) -> str:
        return f"{self.shadow_base}/get/accepted"

    @property
    def topic_shadow_get_rejected(self) -> str:
        return f"{self.shadow_base}/get/rejected"

    @property
    def topic_shadow_update_accepted(self) -> str:
        return f"{self.shadow_base}/update/accepted"

    @property
    def topic_shadow_update_rejected(self) -> str:
        return f"{self.shadow_base}/update/rejected"

    def problems(self) -> list[str]:
        """Lista de problemas de configuración (vacía si todo está bien)."""
        found: list[str] = []
        if not self.endpoint:
            found.append("Falta AWS_IOT_ENDPOINT (endpoint de AWS IoT Core).")
        for label, p in (("CA raíz", self.ca_path), ("certificado", self.cert_path),
                         ("clave privada", self.key_path)):
            if not p.is_file():
                found.append(f"No existe el archivo de {label}: {p}")
        return found


# --------------------------------------------------------------------------- #
# Modelos de datos
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Reading:
    cm: float
    received_at: float


@dataclass(frozen=True)
class LedReport:
    """Último estado de un LED reportado por el dispositivo (confirmación real)."""

    state: str
    received_at: float


@dataclass(frozen=True)
class ShadowSnapshot:
    reported: dict
    desired: dict
    delta: dict
    version: int | None
    received_at: float


@dataclass(frozen=True)
class LedResult:
    """Resultado de pedir un cambio de LED: enviado y/o confirmado."""

    color: str
    requested: str
    sent: bool
    confirmed: bool
    detail: str = ""


# --------------------------------------------------------------------------- #
# Utilidades de normalización
# --------------------------------------------------------------------------- #
_COLOR_ALIASES = {"red": "rojo", "green": "verde", "yellow": "amarillo"}
_STATE_ON = {"on", "encender", "enciende", "prender", "prende", "1", "true"}
_STATE_OFF = {"off", "apagar", "apaga", "0", "false"}


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text).strip().lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def normalize_color(color: str, valid: tuple[str, ...]) -> str | None:
    value = _COLOR_ALIASES.get(_clean(color), _clean(color))
    return value if value in valid else None


def normalize_state(state: str) -> str | None:
    value = _clean(state)
    if value in _STATE_ON:
        return "on"
    if value in _STATE_OFF:
        return "off"
    return None


def parse_distance(payload: bytes) -> float | None:
    """Extrae los cm de ``{"cm": 42.7}``; también acepta un número suelto."""
    try:
        data = json.loads(payload.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError:
        return None
    value = data.get("cm") if isinstance(data, dict) else data
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


# --------------------------------------------------------------------------- #
# Puente MQTT
# --------------------------------------------------------------------------- #
def default_client_factory(settings: Settings):
    """Crea el cliente Paho con TLS mutuo (importación diferida para poder probar sin Paho)."""
    import paho.mqtt.client as mqtt

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.client_id,
    )
    client.tls_set(
        ca_certs=str(settings.ca_path),
        certfile=str(settings.cert_path),
        keyfile=str(settings.key_path),
    )
    return client


class AwsIotBridge:
    """Cliente MQTT/TLS en segundo plano con estado compartido y thread-safe."""

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[[Settings], object] = default_client_factory,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._s = settings
        self._clock = clock
        self._cond = threading.Condition()
        self._connected = False
        self._distance: Reading | None = None
        self._led_reports: dict[str, LedReport] = {}
        self._snapshot: ShadowSnapshot | None = None
        self._snapshot_seq = 0
        self._shadow_error: str | None = None

        self._client = client_factory(settings)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_subscribe = self._on_subscribe
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

    # -- ciclo de vida ------------------------------------------------------ #
    def start(self) -> None:
        logger.info("Conectando a AWS IoT %s:%d como '%s'", self._s.endpoint, self._s.port,
                    self._s.client_id)
        self._client.connect_async(self._s.endpoint, self._s.port, self._s.keepalive)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    # -- suscripciones ------------------------------------------------------ #
    def subscription_topics(self) -> list[str]:
        topics = [self._s.topic_distance]
        if self._s.shadow_enabled:
            topics += [self._s.topic_shadow_update_accepted, self._s.topic_shadow_get_accepted]
            if self._s.shadow_rejected:
                topics += [self._s.topic_shadow_update_rejected,
                           self._s.topic_shadow_get_rejected]
        return topics

    # -- callbacks de Paho (VERSION2) --------------------------------------- #
    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        if getattr(reason_code, "is_failure", False):
            logger.error("AWS IoT rechazó la conexión: %s (¿política o certificado?)", reason_code)
            return
        logger.info("Conectado a AWS IoT Core")
        with self._cond:
            self._connected = True
            self._cond.notify_all()
        # Suscribir en CADA conexión garantiza la re-suscripción tras una reconexión.
        for topic in self.subscription_topics():
            client.subscribe(topic, qos=0)

    def _on_disconnect(self, client, userdata, *args) -> None:
        with self._cond:
            self._connected = False
            self._cond.notify_all()
        logger.warning("Desconectado de AWS IoT; Paho reintentará automáticamente")

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties=None) -> None:
        for rc in reason_codes or []:
            if getattr(rc, "is_failure", False):
                logger.error("Suscripción rechazada (%s). Revisa la política del servidor.", rc)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            self.handle_message(msg.topic, bytes(msg.payload))
        except Exception:  # un mensaje malo no debe tumbar el hilo de red
            logger.exception("Error procesando mensaje en %s", msg.topic)

    # -- procesamiento de mensajes (lógica pura, probada en tests) ---------- #
    def handle_message(self, topic: str, payload: bytes) -> None:
        s = self._s
        now = self._clock()
        if topic == s.topic_distance:
            cm = parse_distance(payload)
            if cm is None:
                logger.warning("Distancia inválida: %r", payload[:60])
                return
            with self._cond:
                self._distance = Reading(cm, now)
            return

        if topic in (s.topic_shadow_update_rejected, s.topic_shadow_get_rejected):
            logger.warning("Shadow rechazado en %s: %r", topic, payload[:200])
            with self._cond:
                self._shadow_error = f"AWS rechazó la operación Shadow ({topic.rsplit('/', 2)[-2]})"
                self._cond.notify_all()
            return

        if topic not in (s.topic_shadow_update_accepted, s.topic_shadow_get_accepted):
            return
        try:
            doc = json.loads(payload.decode("utf-8", errors="replace"))
            state = doc.get("state", {}) if isinstance(doc, dict) else {}
        except json.JSONDecodeError:
            logger.warning("JSON inválido en %s", topic)
            return

        def leds_of(section: str) -> dict:
            leds = (state.get(section) or {}).get("leds") if isinstance(state, dict) else None
            return {k: v for k, v in leds.items() if isinstance(v, str)} if isinstance(leds, dict) else {}

        with self._cond:
            if topic == s.topic_shadow_update_accepted:
                # Lo reportado por el dispositivo = confirmación física del cambio.
                for color, value in leds_of("reported").items():
                    self._led_reports[color] = LedReport(value, now)
            else:
                self._snapshot = ShadowSnapshot(
                    reported=leds_of("reported"),
                    desired=leds_of("desired"),
                    delta=leds_of("delta"),
                    version=doc.get("version") if isinstance(doc, dict) else None,
                    received_at=now,
                )
                self._snapshot_seq += 1
                self._shadow_error = None
            self._cond.notify_all()

    # -- consultas ---------------------------------------------------------- #
    @property
    def connected(self) -> bool:
        with self._cond:
            return self._connected

    def last_distance(self) -> tuple[Reading | None, float | None]:
        with self._cond:
            reading = self._distance
        if reading is None:
            return None, None
        return reading, self._clock() - reading.received_at

    def led_reports(self) -> dict[str, tuple[str, float]]:
        """Último estado reportado por el ESP32 por LED: {color: (estado, antigüedad_s)}."""
        now = self._clock()
        with self._cond:
            return {c: (r.state, now - r.received_at) for c, r in self._led_reports.items()}

    # -- publicación -------------------------------------------------------- #
    def _publish(self, topic: str, payload: str) -> tuple[bool, str]:
        if not self.connected:
            return False, "No hay conexión con AWS IoT Core."
        info = self._client.publish(topic, payload, qos=1)
        rc = getattr(info, "rc", 0)
        if rc != 0:
            logger.error("Fallo al publicar en %s (código %s)", topic, rc)
            return False, f"Error al publicar (código MQTT {rc})."
        logger.info("Publicado en %s: %s", topic, payload)
        return True, payload

    def publish_command(self, color: str, state: str) -> tuple[bool, str]:
        """Publica un comando de LED (solo 'enviado', NO confirma nada)."""
        payload = json.dumps({"led": color, "estado": state}, separators=(",", ":"))
        return self._publish(self._s.topic_command, payload)

    def send_led_commands(
        self, changes: list[tuple[str, str]], timeout_s: float | None = None
    ) -> list[LedResult]:
        """Envía cambios de LED y espera la confirmación del dispositivo.

        Un cambio queda *confirmado* solo si el ESP32 reporta, DESPUÉS del envío,
        el estado pedido en el Shadow. Si no llega a tiempo, queda "enviado sin confirmar".
        """
        timeout = self._s.confirm_timeout_s if timeout_s is None else timeout_s
        t0 = self._clock()
        results: dict[str, LedResult] = {}
        for color, state in changes:
            ok, detail = self.publish_command(color, state)
            results[color] = LedResult(color, state, ok, False, "" if ok else detail)

        if not self._s.shadow_enabled:
            return list(results.values())  # sin Shadow no hay forma de confirmar

        deadline = t0 + timeout

        def satisfied(color: str, state: str) -> bool:
            rep = self._led_reports.get(color)
            return rep is not None and rep.state == state and rep.received_at >= t0

        with self._cond:
            pending = {c: r for c, r in results.items() if r.sent}
            while pending:
                for color in [c for c, r in pending.items() if satisfied(c, r.requested)]:
                    results[color] = LedResult(color, pending[color].requested, True, True)
                    del pending[color]
                remaining = deadline - self._clock()
                if not pending or remaining <= 0:
                    break
                self._cond.wait(remaining)
        return [results[c] for c, _ in changes]

    def request_shadow(self, timeout_s: float = 4.0) -> tuple[ShadowSnapshot | None, str]:
        """Consulta el Shadow (publica en shadow/get y espera get/accepted)."""
        if not self._s.shadow_enabled:
            return None, "El Shadow está deshabilitado (SHADOW_ENABLED=false)."
        with self._cond:
            seq0 = self._snapshot_seq
            self._shadow_error = None
        ok, detail = self._publish(self._s.topic_shadow_get, "")
        if not ok:
            return None, detail
        deadline = self._clock() + timeout_s
        with self._cond:
            while self._snapshot_seq == seq0 and self._shadow_error is None:
                remaining = deadline - self._clock()
                if remaining <= 0:
                    return None, "AWS no respondió a tiempo (¿el Shadow aún no existe o falta permiso?)."
                self._cond.wait(remaining)
            if self._shadow_error:
                return None, self._shadow_error
            return self._snapshot, ""
