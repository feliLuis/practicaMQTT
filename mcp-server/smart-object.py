#!/usr/bin/env python3
"""Servidor MCP del objeto inteligente (SIS-234, Práctica MQTT).

Este programa actúa como puente entre una herramienta de IA (p. ej. Claude
Desktop) y el objeto inteligente (ESP32), usando un broker MQTT en la nube:

    Claude Desktop <--MCP/stdio--> este servidor <--MQTT--> broker <--> ESP32

Responsabilidades:
  * Suscribirse al tópico de distancia y recordar la última lectura.
  * Publicar comandos JSON para los actuadores (LEDs y/o servomotor).
  * Exponer ambas capacidades como herramientas MCP.

Notas importantes:
  * El transporte MCP es stdio: NUNCA usar ``print()`` (corrompe el protocolo).
    Todos los mensajes de log salen por ``logging`` hacia stderr.
  * La configuración se lee de variables de entorno o de un archivo ``.env``
    (excluido de Git). Ver ``.env.example``.

Contrato de mensajes (debe coincidir con el firmware del ESP32):
  * ``<prefijo>/distancia``         ESP32 -> broker : ``{"cm": 42.7}``
  * ``<prefijo>/actuadores/cmd``    broker -> ESP32 : ``{"led": "rojo", "estado": "on"}``
                                                      ``{"servo": 90}``
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

import paho.mqtt.client as mqtt

# El SDK oficial de MCP 2.x expone MCPServer; versiones anteriores y el paquete
# independiente "fastmcp" exponen FastMCP. Se acepta cualquiera de los tres.
try:
    from mcp.server import MCPServer as ServerClass
except ImportError:  # pragma: no cover - depende de la versión instalada
    try:
        from mcp.server.fastmcp import FastMCP as ServerClass
    except ImportError:
        from fastmcp import FastMCP as ServerClass

# --------------------------------------------------------------------------- #
# Logging (a stderr, nunca a stdout)
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smart-object")


# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
def load_dotenv(path: Path) -> None:
    """Carga pares CLAVE=valor de un archivo .env sin pisar variables ya definidas."""
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
    """Parámetros de configuración del servidor."""

    broker_host: str
    broker_port: int
    keepalive: int
    username: str
    password: str
    topic_prefix: str
    leds: tuple[str, ...]
    servo_enabled: bool
    stale_after_s: float

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path(__file__).with_name(".env"))
        leds = tuple(
            c.strip().lower()
            for c in os.environ.get("LED_COLORS", "rojo,verde,amarillo").split(",")
            if c.strip()
        )
        return cls(
            broker_host=os.environ.get("MQTT_BROKER", "broker.hivemq.com"),
            broker_port=int(os.environ.get("MQTT_PORT", "1883")),
            keepalive=int(os.environ.get("MQTT_KEEPALIVE", "60")),
            username=os.environ.get("MQTT_USER", ""),
            password=os.environ.get("MQTT_PASSWORD", ""),
            topic_prefix=os.environ.get("TOPIC_PREFIX", "sis234/grupoN").strip("/"),
            leds=leds,
            servo_enabled=_env_bool("SERVO_ENABLED", False),
            stale_after_s=float(os.environ.get("STALE_AFTER_S", "5")),
        )

    @property
    def topic_distance(self) -> str:
        return f"{self.topic_prefix}/distancia"

    @property
    def topic_command(self) -> str:
        return f"{self.topic_prefix}/actuadores/cmd"


# --------------------------------------------------------------------------- #
# Cliente MQTT
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Reading:
    """Una lectura de distancia con el instante (monótono) en que se recibió."""

    cm: float
    received_at: float


class MqttBridge:
    """Cliente MQTT en segundo plano: guarda la última distancia y publica comandos."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._reading: Reading | None = None
        self._connected = threading.Event()

        # Un client_id único evita expulsiones mutuas en el broker público.
        client_id = f"mcp-{uuid.uuid4().hex[:8]}"
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        if settings.username:
            self._client.username_pw_set(settings.username, settings.password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        # Reconexión automática con espera creciente entre 1 y 30 s.
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

    # -- ciclo de vida ------------------------------------------------------ #
    def start(self) -> None:
        """Inicia la conexión de forma asíncrona y el hilo de red de Paho."""
        logger.info(
            "Conectando a %s:%d (tópico distancia: %s)",
            self._settings.broker_host,
            self._settings.broker_port,
            self._settings.topic_distance,
        )
        self._client.connect_async(
            self._settings.broker_host,
            self._settings.broker_port,
            self._settings.keepalive,
        )
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    # -- callbacks de Paho -------------------------------------------------- #
    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            logger.error("No se pudo conectar al broker: %s", reason_code)
            return
        logger.info("Conectado al broker MQTT")
        self._connected.set()
        # Suscribir aquí garantiza la re-suscripción tras cada reconexión.
        client.subscribe(self._settings.topic_distance, qos=0)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        self._connected.clear()
        logger.warning("Desconectado del broker (%s). Paho reintentará solo.", reason_code)

    def _on_message(self, client, userdata, msg) -> None:
        cm = self.parse_distance(msg.payload)
        if cm is None:
            logger.warning("Mensaje de distancia inválido en %s: %r", msg.topic, msg.payload[:60])
            return
        with self._lock:
            self._reading = Reading(cm=cm, received_at=time.monotonic())

    # -- utilidades --------------------------------------------------------- #
    @staticmethod
    def parse_distance(payload: bytes) -> float | None:
        """Extrae los cm de ``{"cm": 42.7}``; también acepta un número suelto."""
        text = payload.decode("utf-8", errors="replace").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        value = data.get("cm") if isinstance(data, dict) else data
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    # -- API pública -------------------------------------------------------- #
    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def last_reading(self) -> tuple[Reading | None, float | None]:
        """Devuelve (última lectura, antigüedad en segundos)."""
        with self._lock:
            reading = self._reading
        if reading is None:
            return None, None
        return reading, time.monotonic() - reading.received_at

    def publish_command(self, command: dict) -> tuple[bool, str]:
        """Publica un comando JSON para el objeto inteligente (QoS 1)."""
        if not self.connected:
            return False, "El servidor MCP no está conectado al broker MQTT."
        payload = json.dumps(command, separators=(",", ":"), ensure_ascii=False)
        info = self._client.publish(self._settings.topic_command, payload, qos=1)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            error = mqtt.error_string(info.rc)
            logger.error("Fallo al publicar %s: %s", payload, error)
            return False, f"Error al publicar el comando: {error}"
        logger.info("Comando publicado en %s: %s", self._settings.topic_command, payload)
        return True, payload


# --------------------------------------------------------------------------- #
# Normalización de lo que escribe el usuario / el modelo
# --------------------------------------------------------------------------- #
_COLOR_ALIASES = {
    "red": "rojo", "green": "verde", "yellow": "amarillo",
    "blue": "azul", "white": "blanco", "orange": "naranja",
}
_STATE_ON = {"on", "encender", "enciende", "prender", "prende", "1", "true"}
_STATE_OFF = {"off", "apagar", "apaga", "0", "false"}


def _clean(text: str) -> str:
    """Minúsculas y sin tildes, para comparar 'Amarillo' con 'amarillo'."""
    text = unicodedata.normalize("NFD", text.strip().lower())
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


# --------------------------------------------------------------------------- #
# Servidor MCP
# --------------------------------------------------------------------------- #
def create_server(settings: Settings, bridge: MqttBridge) -> ServerClass:
    """Construye el servidor MCP y registra las herramientas del objeto inteligente."""
    mcp = ServerClass("smart-object")
    colors_txt = ", ".join(settings.leds)

    def _send_leds(changes: list[tuple[str, str]]) -> str:
        """Envía varios cambios (color, estado) y resume el resultado."""
        for color, state in changes:
            ok, detail = bridge.publish_command({"led": color, "estado": state})
            if not ok:
                return detail
        summary = ", ".join(f"{c}={s}" for c, s in changes)
        return f"Comandos enviados al objeto inteligente: {summary}."

    @mcp.tool()
    def get_distance() -> str:
        """Obtiene la distancia más reciente (en centímetros) medida por el sensor
        ultrasónico del objeto inteligente. Úsala cuando pregunten a qué distancia
        está un objeto o cuál es la lectura actual del sensor."""
        reading, age = bridge.last_reading()
        if reading is None:
            return (
                "Aún no se recibió ninguna lectura. Verifica que el ESP32 esté "
                f"encendido y conectado (broker conectado: {bridge.connected})."
            )
        text = f"Distancia: {reading.cm:.1f} cm (lectura de hace {age:.1f} s)."
        if age > settings.stale_after_s:
            text += " Aviso: la lectura es antigua, el objeto podría estar desconectado."
        return text

    @mcp.tool()
    def set_led(color: str, state: str) -> str:
        """Enciende o apaga UN LED del objeto inteligente sin tocar los demás.

        Args:
            color: Color del LED (por defecto: rojo, verde o amarillo).
            state: "on" para encender, "off" para apagar.
        """
        led = normalize_color(color, settings.leds)
        if led is None:
            return f"Color no válido: '{color}'. Opciones: {colors_txt}."
        value = normalize_state(state)
        if value is None:
            return f"Estado no válido: '{state}'. Usa 'on' u 'off'."
        return _send_leds([(led, value)])

    @mcp.tool()
    def only_led(color: str) -> str:
        """Enciende SOLO el LED indicado y apaga todos los demás. Úsala para
        instrucciones como 'enciende el LED rojo y apaga los demás'.

        Args:
            color: Color del LED que debe quedar encendido (rojo, verde o amarillo).
        """
        target = normalize_color(color, settings.leds)
        if target is None:
            return f"Color no válido: '{color}'. Opciones: {colors_txt}."
        changes = [(c, "off") for c in settings.leds if c != target] + [(target, "on")]
        return _send_leds(changes)

    @mcp.tool()
    def all_leds_off() -> str:
        """Apaga todos los LEDs del objeto inteligente."""
        return _send_leds([(c, "off") for c in settings.leds])

    @mcp.tool()
    def all_leds_on() -> str:
        """Enciende todos los LEDs del objeto inteligente."""
        return _send_leds([(c, "on") for c in settings.leds])

    if settings.servo_enabled:

        @mcp.tool()
        def move_servo(angle: int) -> str:
            """Mueve el servomotor del objeto inteligente a un ángulo.

            Args:
                angle: Ángulo en grados, entre 0 y 180.
            """
            if not 0 <= angle <= 180:
                return f"Ángulo fuera de rango: {angle}. Debe estar entre 0 y 180."
            ok, detail = bridge.publish_command({"servo": int(angle)})
            return f"Servomotor movido a {int(angle)}°." if ok else detail

    @mcp.tool()
    def get_system_status() -> str:
        """Informa el estado de la conexión con el broker MQTT y de la última
        lectura del sensor. Útil para diagnosticar si el sistema está operativo."""
        reading, age = bridge.last_reading()
        sensor = "sin lecturas" if reading is None else f"{reading.cm:.1f} cm hace {age:.1f} s"
        return (
            f"Broker MQTT: {'conectado' if bridge.connected else 'DESCONECTADO'} "
            f"({settings.broker_host}). Sensor: {sensor}. "
            f"LEDs: {colors_txt}. Servo: {'sí' if settings.servo_enabled else 'no'}."
        )

    return mcp


# --------------------------------------------------------------------------- #
# Punto de entrada
# --------------------------------------------------------------------------- #
def main() -> None:
    settings = Settings.from_env()
    if settings.topic_prefix.endswith("grupoN"):
        logger.warning("TOPIC_PREFIX usa el valor por defecto '%s'; cámbialo por uno único.",
                       settings.topic_prefix)
    bridge = MqttBridge(settings)
    server = create_server(settings, bridge)
    bridge.start()
    try:
        server.run(transport="stdio")  # bloquea: el programa corre todo el tiempo
    except KeyboardInterrupt:
        logger.info("Interrumpido, cerrando.")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
