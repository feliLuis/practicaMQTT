# Guía de implementación (en orden)

Tiempo orientativo total: 5–7 h. Marca cada paso al terminarlo.

## 0. Preparar el repositorio
- [ ] Descomprimir y subir a GitHub. Cada integrante hace **commits con su propia cuenta**.
- [ ] `git status`: **no** deben aparecer `config.h`, `aws_certificates.h`, `.env`, `*.pem`, `*.key`.
- [ ] Si algún certificado/clave ya estuvo en un commit antiguo, desactívalo en AWS y crea otro (borrar el archivo no limpia el historial).

## 1. AWS (≈ 40 min) → `docs/AWS_CONFIGURACION.md`
- [ ] Verificar `PoliticaESP32SIS234` contra la tabla del §2.
- [ ] Crear la identidad del servidor MCP (política `PoliticaServidorMCP` + certificado + `mcp-sis234`).
- [ ] Crear la identidad de la app (`PoliticaAppMovil` + certificado + `app-sis234`).

## 2. Circuito (≈ 30 min) → `docs/CIRCUITO.md`
- [ ] Verificar divisor del ECHO, resistencias de LEDs y GND común.
- [ ] Confirmar los pines reales en `config.h`.

## 3. Firmware (≈ 1–2 h) → `docs/PRUEBAS.md §B`
1. `firmware/include/config.example.h` → `config.h`: completar `WIFI_SSID` y `WIFI_PASSWORD`; revisar pines.
2. `aws_certificates.example.h` → `aws_certificates.h`: pegar `AmazonRootCA1.pem`, `certificate.pem` y `private.pem.key` completos, con sus líneas BEGIN/END.
3. Abrir **la carpeta `firmware/`** en VS Code (PlatformIO solo detecta `platformio.ini` en la raíz abierta).
4. Compilar → cargar → monitor. Si hay errores de compilación, corregirlos (el código no fue compilado).
5. Verificar T1–T9 de `PRUEBAS.md`.

## 4. Servidor MCP (≈ 45 min) → `mcp-server/README.md`
1. Copiar los 3 archivos de la identidad del servidor a `mcp-server/certs/`.
2. `cp .env.example .env`.
3. `uv sync`, y comprobar que `uv run python -m unittest discover -s tests` pasa.
4. `uv run smart-object.py` para ver el log de conexión (sale con error claro si faltan archivos). Detener con Ctrl+C.
5. Registrar en Claude Desktop con `config/claude_desktop_config.example.json` (ruta absoluta), reiniciar y probar T12–T17.

## 5. App móvil (≈ 45 min) → `docs/APP_MOVIL.md`
- [ ] Paso 1 de la guía: ¿la app admite certificado de cliente? Si no, elegir alternativa.
- [ ] Crear el panel (gráfico + 3 switches) y exportarlo a `config/`.

## 6. Medir requerimientos no funcionales (≈ 45 min) → `docs/PRUEBAS.md §D`
- [ ] Anotar los valores medidos y declararlos en el README.

## 7. Cierre
- [ ] Completar integrantes y valores en `README.md`.
- [ ] `git grep -iE "BEGIN (RSA )?PRIVATE|password"` sin resultados reales.
- [ ] Comprobar que el enlace abre sin sesión (o que el docente tiene acceso).
- [ ] Enviar el enlace por el LMS **antes del plazo**.
- [ ] Ensayar la demo (incluida la reconexión) y la defensa: cada integrante debe poder explicar el circuito, TLS, el Shadow, el flujo de confirmación y el servidor MCP.

## Preguntas probables de la defensa
- ¿Por qué TLS con certificado de cliente y por qué necesita la hora (NTP)?
- ¿Qué diferencia hay entre enviar un comando y confirmarlo? ¿Cómo lo resuelven?
- ¿Para qué sirven `desired`, `reported` y `delta`? ¿Por qué un comando directo también escribe `desired`?
- ¿Por qué el servidor MCP tiene su propio certificado y política?
- ¿Qué pasa si se cae el WiFi o el broker? ¿Cómo se re-suscribe?
- ¿Por qué no se usa `print()` en el servidor MCP?
- ¿Por qué el ECHO necesita divisor de voltaje y por qué se usa la mediana?
