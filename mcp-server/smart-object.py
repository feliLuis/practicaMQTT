#!/usr/bin/env python3
"""Servidor MCP del objeto inteligente (SIS-234) sobre AWS IoT Core.

    Claude Desktop <--MCP/stdio--> este servidor <--MQTT/TLS--> AWS IoT Core <--> ESP32

La lógica de red vive en ``aws_iot_bridge.py``; aquí solo se declaran las
herramientas MCP y se da formato a sus respuestas.

IMPORTANTE: el transporte es stdio, por lo que NUNCA se debe usar ``print()``
(corrompe el protocolo). Todo log sale por ``logging`` hacia stderr.
"""

from __future__ import annotations

import logging
import os
import sys

from aws_iot_bridge import (
    AwsIotBridge,
    LedResult,
    Settings,
    normalize_color,
    normalize_state,
)

# MCP SDK 2.x expone MCPServer; versiones anteriores y el paquete "fastmcp" exponen FastMCP.
try:
    from mcp.server import MCPServer as ServerClass
except ImportError:  # pragma: no cover - depende de la versión instalada
    try:
        from mcp.server.fastmcp import FastMCP as ServerClass
    except ImportError:
        from fastmcp import FastMCP as ServerClass

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smart-object")


def format_results(results: list[LedResult], timeout_s: float) -> str:
    """Texto que distingue 'enviado' de 'confirmado por el dispositivo'."""
    lines = []
    for r in results:
        if not r.sent:
            lines.append(f"- {r.color} -> {r.requested.upper()}: NO ENVIADO ({r.detail})")
        elif r.confirmed:
            lines.append(f"- {r.color} -> {r.requested.upper()}: CONFIRMADO por el ESP32")
        else:
            lines.append(
                f"- {r.color} -> {r.requested.upper()}: enviado, SIN confirmar "
                f"(el ESP32 no reportó el cambio en {timeout_s:g} s)"
            )
    if any(r.sent and not r.confirmed for r in results):
        lines.append(
            "Aviso: 'enviado' solo significa que AWS aceptó el mensaje; no se puede asegurar "
            "que el LED haya cambiado físicamente."
        )
    return "\n".join(lines)


def create_server(settings: Settings, bridge: AwsIotBridge) -> ServerClass:
    """Construye el servidor MCP y registra sus herramientas."""
    mcp = ServerClass("smart-object")
    colors_txt = ", ".join(settings.leds)

    @mcp.tool()
    def get_distance() -> str:
        """Devuelve la última distancia válida (en cm) medida por el sensor ultrasónico
        del objeto inteligente, con su antigüedad. Úsala cuando pregunten a qué
        distancia está el objeto."""
        reading, age = bridge.last_distance()
        if reading is None:
            return ("Aún no se recibió ninguna lectura. Verifica que el ESP32 esté encendido "
                    f"y conectado (conexión con AWS IoT: {'sí' if bridge.connected else 'NO'}).")
        text = f"Distancia: {reading.cm:.1f} cm (lectura de hace {age:.1f} s)."
        if age > settings.stale_after_s:
            text += " Aviso: la lectura es antigua; el ESP32 podría estar desconectado."
        return text

    @mcp.tool()
    def get_system_status() -> str:
        """Informa la conexión con AWS IoT Core, la antigüedad de la última lectura del
        sensor y el último estado de los LEDs reportado por el dispositivo."""
        reading, age = bridge.last_distance()
        if reading is None:
            sensor = "sin lecturas"
        else:
            fresh = "al día" if age <= settings.stale_after_s else "ANTIGUA"
            sensor = f"{reading.cm:.1f} cm, hace {age:.1f} s ({fresh})"
        reports = bridge.led_reports()
        leds = ", ".join(f"{c}={s} (hace {a:.0f} s)" for c, (s, a) in sorted(reports.items()))
        return (
            f"AWS IoT Core: {'conectado' if bridge.connected else 'DESCONECTADO'} "
            f"({settings.endpoint}). Sensor: {sensor}. "
            f"LEDs reportados por el dispositivo: {leds or 'ninguno aún'}."
        )

    @mcp.tool()
    def set_led(color: str, state: str) -> str:
        """Enciende o apaga UN LED sin tocar los demás y espera la confirmación del ESP32.

        Args:
            color: rojo, verde o amarillo.
            state: "on" para encender, "off" para apagar.
        """
        led = normalize_color(color, settings.leds)
        if led is None:
            return f"Color no válido: '{color}'. Opciones: {colors_txt}."
        value = normalize_state(state)
        if value is None:
            return f"Estado no válido: '{state}'. Usa 'on' u 'off'."
        return format_results(bridge.send_led_commands([(led, value)]), settings.confirm_timeout_s)

    @mcp.tool()
    def only_led(color: str) -> str:
        """Enciende SOLO el LED indicado y apaga los demás ("enciende el rojo y apaga los
        demás"). Espera la confirmación del ESP32.

        Args:
            color: rojo, verde o amarillo.
        """
        target = normalize_color(color, settings.leds)
        if target is None:
            return f"Color no válido: '{color}'. Opciones: {colors_txt}."
        changes = [(c, "off") for c in settings.leds if c != target] + [(target, "on")]
        return format_results(bridge.send_led_commands(changes), settings.confirm_timeout_s)

    @mcp.tool()
    def all_leds_on() -> str:
        """Enciende todos los LEDs y espera la confirmación del ESP32."""
        changes = [(c, "on") for c in settings.leds]
        return format_results(bridge.send_led_commands(changes), settings.confirm_timeout_s)

    @mcp.tool()
    def all_leds_off() -> str:
        """Apaga todos los LEDs y espera la confirmación del ESP32."""
        changes = [(c, "off") for c in settings.leds]
        return format_results(bridge.send_led_commands(changes), settings.confirm_timeout_s)

    if settings.shadow_enabled:

        @mcp.tool()
        def get_shadow_state() -> str:
            """Consulta en AWS el Device Shadow del objeto: estado de los LEDs reportado
            por el dispositivo (reported), el deseado (desired) y las diferencias (delta).
            Requiere permisos de Shadow en la política del servidor."""
            snap, error = bridge.request_shadow()
            if snap is None:
                return f"No se pudo leer el Shadow: {error}"
            delta = snap.delta or "ninguna (reported = desired)"
            return (f"Shadow (versión {snap.version}): reported={snap.reported}, "
                    f"desired={snap.desired}, diferencias pendientes={delta}.")

    return mcp


def main() -> None:
    settings = Settings.from_env()
    problems = settings.problems()
    if problems:
        for p in problems:
            logger.error(p)
        logger.error("Corrige la configuración (ver mcp-server/README.md y docs/AWS_CONFIGURACION.md).")
        sys.exit(1)

    bridge = AwsIotBridge(settings)
    server = create_server(settings, bridge)
    bridge.start()
    try:
        server.run(transport="stdio")  # bloquea: el servidor corre todo el tiempo
    except KeyboardInterrupt:
        logger.info("Interrumpido, cerrando.")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
