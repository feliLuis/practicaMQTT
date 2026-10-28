# Qué falta por hacer

**Entrega: jueves 29/10/2026, 17:45 — enlace del repo por el LMS-UCB.**
Leyenda: ✅ hecho · 🟡 hecho pero **sin probar** · ⬜ pendiente (lo haces tú)

## Estado actual

| Parte | Estado |
|---|---|
| Servidor MCP (`mcp-server/`) | 🟡 Escrito; falta probarlo con `uv sync` y Claude Desktop |
| Simulador del ESP32 | 🟡 Escrito; falta probarlo |
| Firmware ESP32 (`firmware/`) | 🟡 Escrito, **no compilado**: puede necesitar ajustes menores |
| Circuito | ⬜ |
| App móvil | ⬜ |
| Mediciones no funcionales | ⬜ |
| README final y repositorio | ⬜ |

## Orden recomendado

### Bloque 1 — Servidor MCP con el simulador (≈ 45 min)
- ⬜ Instalar `uv` y Python ≥ 3.10.
- ⬜ En `mcp-server/`: `uv sync`; copiar `.env.example` → `.env` y poner su `TOPIC_PREFIX` único.
- ⬜ Ejecutar `uv run python simulate_esp32.py --prefix <su prefijo>` en una terminal.
- ⬜ Registrar el servidor en Claude Desktop (`config/claude_desktop_config.example.json`, con ruta absoluta) y reiniciarlo.
- ⬜ Probar: "¿A qué distancia está el objeto?" y "Enciende el LED rojo y apaga los demás" (el simulador debe mostrar los comandos).
- ⬜ Si algo falla: revisar `%APPDATA%\Claude\logs\mcp-server-smart-object.log` y pegarme el error.

### Bloque 2 — Repositorio (≈ 20 min, **háganlo ya** para que los commits cuenten)
- ⬜ Crear el repo en GitHub y subir esta carpeta.
- ⬜ Cada integrante clona y hace **commits con su propia cuenta**, con mensajes claros.
- ⬜ Verificar que `.env` y `firmware/include/config.h` NO están en el repo.

### Bloque 3 — Hardware y firmware (≈ 2–3 h)
- ⬜ Armar el circuito: HC-SR04 (¡ECHO con divisor 1 kΩ/2 kΩ!), 3 LEDs con resistencias de 220 Ω (GPIO 25, 26, 27).
- ⬜ Copiar `firmware/include/config.example.h` → `config.h`; completar Wi-Fi, `TOPIC_PREFIX` (el mismo que en el servidor) y pines.
- ⬜ `pio run`; corregir errores de compilación si aparecen.
- ⬜ Subir y revisar el monitor serie: ¿conecta a Wi-Fi y MQTT? ¿publica distancias?
- ⬜ Verificar que los LEDs funcionan; si prenden al revés, poner `LED_ACTIVE_LOW 1`.
- ⬜ Decidir: ¿LEDs o servo? Si servo, ver la guía (sección 3, paso 6).

### Bloque 4 — App móvil (≈ 45 min)
- ⬜ IoT MQTT Panel: conexión a `broker.hivemq.com:1883`.
- ⬜ Widget **gráfico** (gauge o línea) para `<prefijo>/distancia` (RF4: no puede ser solo texto).
- ⬜ Un switch por LED publicando `{"led":"rojo","estado":"on"}` / `...off`.
- ⬜ Exportar el panel a `config/` (si la app lo permite).

### Bloque 5 — Integración completa (≈ 30 min)
- ⬜ Cerrar el simulador y usar el ESP32 real con Claude Desktop, la app y el servidor a la vez.
- ⬜ Repetir las 3 instrucciones de lenguaje natural de la práctica.

### Bloque 6 — Medición de requerimientos no funcionales (≈ 45 min)
- ⬜ **Estabilidad:** ≥ 10 min sin reinicios.
- ⬜ **Exactitud:** cinta métrica a 10, 20, 50 y 100 cm; error ≤ ±3 cm. Si hay más error, ajustar `SENSOR_SAMPLES` o revisar el montaje.
- ⬜ **Respuesta:** app → LED en ≤ 1 s (video del teléfono).
- ⬜ **Frecuencia:** ≥ 2 lecturas/s.
- ⬜ **Reconexión:** apagar/encender el hotspot y comprobar que vuelve solo.
- ⬜ Declarar el **rango de trabajo** real.

### Bloque 7 — Cierre (≈ 45 min)
- ⬜ Completar `README.md` (integrantes, prefijo, valores medidos).
- ⬜ `git grep -i password` para revisar que no haya credenciales.
- ⬜ Confirmar que el enlace del repo abre **sin iniciar sesión** (o que el docente tiene acceso).
- ⬜ **Enviar el enlace por el LMS con margen antes de las 17:45.**
- ⬜ Ensayar la demo completa y la defensa (preguntas al final de `GUIA_IMPLEMENTACION.md`).

## Riesgos a vigilar
1. **El firmware no está compilado.** Puede haber errores menores (versiones de librerías). Si pasa, pégame el mensaje de error y lo corrijo.
2. **Broker público:** si otro grupo usa el mismo prefijo, verán comandos cruzados. Usen un prefijo único.
3. **Pin ECHO sin divisor de voltaje** puede dañar el ESP32.
4. **Defensa individual (50 % de la nota):** ambos deben entender todo, no solo su parte. Cada uno debe tener commits propios.
5. **Dependencia de la versión del SDK de MCP:** el servidor soporta `MCPServer` (SDK 2.x) y `FastMCP`; si `uv sync` instala algo distinto y falla el import, avísame.
