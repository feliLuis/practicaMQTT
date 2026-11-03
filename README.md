# Práctica MQTT — Objeto inteligente con AWS IoT Core y MCP

**Materia:** SIS-234  
**Repositorio:** https://github.com/feliLuis/practicaMQTT

## 1. Descripción

Sistema IoT compuesto por un **ESP32** con sensor ultrasónico **HC-SR04** y tres LEDs (rojo, verde y amarillo). El dispositivo publica mediciones de distancia y recibe comandos mediante **MQTT sobre TLS** a través de **AWS IoT Core**. Un servidor **MCP en Python** permite consultar información y controlar los actuadores desde **Claude Desktop**. La aplicación Android **IoT MQTT Panel** muestra la distancia mediante un indicador gráfico (*gauge*) y ofrece interruptores para los LEDs.

```text
HC-SR04 / LEDs ↔ ESP32 ↔ AWS IoT Core (MQTT/TLS) ↔ Servidor MCP ↔ Claude Desktop
                              ↕
                       IoT MQTT Panel (Android)
```

## 2. Integrantes y responsabilidades

| Integrante | GitHub | Responsabilidades |
|---|---|---|
| Leonardo Koller | [@LeoGKM](https://github.com/LeoGKM) | `firmware/src/`: código principal del ESP32. |
| Luis Felipe Velasco | [@feliLuis](https://github.com/feliLuis) | `firmware/include/`: plantillas `config.example.h` y `aws_certificates.example.h`; participación en la conexión con Claude Desktop. |
| Jesús Ariel Mamani Gutiérrez | [@JesusxAriel](https://github.com/JesusxAriel) | `mcp-server/`, configuración e integración con AWS IoT Core y demás componentes del proyecto. |

## 3. Hardware y software

- **ESP32** con sensor ultrasónico **HC-SR04**: TRIG GPIO27 y ECHO GPIO26.
- **Actuadores:** LED rojo GPIO14, verde GPIO13 y amarillo GPIO12.
- **Firmware:** PlatformIO / Arduino.
- **Mensajería:** AWS IoT Core, región `us-east-2`, MQTT/TLS puerto `8883`.
- **Servidor MCP:** Python, con integración MQTT y herramientas para Claude Desktop.
- **Aplicación móvil:** IoT MQTT Panel (Android).

## 4. Estructura del repositorio

```text
practicaMQTT/
├── firmware/
│   ├── src/                 # Código fuente del ESP32
│   ├── include/             # Plantillas de configuración, sin secretos
│   └── platformio.ini       # Configuración de compilación
├── mcp-server/              # Servidor MCP y puente AWS IoT
├── config/                  # Políticas y configuraciones de referencia
├── docs/                    # Documentación y evidencias
├── .gitignore
└── README.md
```

Los archivos de credenciales locales no forman parte del repositorio. Los módulos contienen el código y las plantillas de configuración utilizadas en la práctica.

## 5. Tópicos MQTT y mensajes

| Tópico | Emisor → receptor | Finalidad | Ejemplo de mensaje |
|---|---|---|---|
| `sis234/esp32/distancia` | ESP32 → clientes suscritos | Publicar distancia en centímetros | `{"cm":25.7}` |
| `sis234/esp32/comandos` | MCP o móvil → ESP32 | Controlar actuadores | `{"led":"rojo","estado":"on"}` |

Comandos de ejemplo:

```json
{"led":"rojo","estado":"on"}
```

```json
{"led":"rojo","estado":"off"}
```

Se utiliza el mismo formato para `verde` y `amarillo`. El ESP32 también utiliza **AWS IoT Device Shadow** para representar estados `desired` y `reported` de los LEDs; los tópicos del Shadow pertenecen al espacio `$aws/things/esp32-sis234/shadow/`.

**Identificadores de cliente MQTT utilizados:** `esp32-sis234` (dispositivo), `mcp-sis234` (servidor MCP) y `movil-sis234` (aplicación móvil). Cada cliente debe tener su certificado y permisos correspondientes.

## 6. Herramientas MCP expuestas

| Herramienta | Parámetros | Propósito |
|---|---|---|
| `get_distance` | Ninguno | Consultar la última medición de distancia disponible. |
| `get_system_status` | Ninguno | Consultar estado de conexión y datos recientes del sistema. |
| `set_led` | `color`, `state` | Encender o apagar un LED específico. |
| `only_led` | `color` | Activar únicamente el LED seleccionado. |
| `all_leds_on` | Ninguno | Encender los tres LEDs. |
| `all_leds_off` | Ninguno | Apagar los tres LEDs. |
| `get_shadow_state` | Ninguno | Consultar el estado del Device Shadow. |

Para `set_led`, los colores esperados son `rojo`, `verde` y `amarillo`, y los estados son `on` y `off`.

## 7. Requerimientos funcionales: aplicación móvil

- **RF4 — Visualización gráfica:** un panel *Gauge* suscrito a `sis234/esp32/distancia`, con extracción JSONPath `$.cm`, unidad `cm` y escala configurada de 0 a 400 cm.
- **RF5 — Control de actuadores:** tres interruptores que publican mensajes JSON `on`/`off` en `sis234/esp32/comandos` para los LEDs rojo, verde y amarillo.

La aplicación móvil se configura en **IoT MQTT Panel**; no se desarrolló una aplicación Android nativa. La configuración del panel se realizó directamente en el teléfono. No se incluye una exportación del dashboard; la sección 9.4 documenta su reproducción manual.

## 8. Características no funcionales y alcance de las pruebas

El sistema se configuró para comunicarse mediante MQTT sobre TLS y certificados X.509. Los siguientes valores corresponden a parámetros efectivamente utilizados en la práctica; no representan resultados de pruebas de rendimiento.

| Característica | Valor utilizado | Resultado observado |
|---|---|---|
| Seguridad del transporte | MQTT sobre TLS, puerto `8883` | Se establecieron conexiones con AWS IoT Core usando certificados. |
| Región de AWS IoT Core | `us-east-2` | Región utilizada durante la implementación. |
| TLS en IoT MQTT Panel | TLS 1.2 | Configuración aplicada en Android. |
| Escala gráfica del sensor | 0–400 cm, una cifra decimal | Gauge configurado para mostrar el valor JSON `cm`. |
| Identidad por componente | Clientes MQTT independientes | Se utilizaron `esp32-sis234`, `mcp-sis234` y `movil-sis234`. |
| Latencia de comandos | Sin medición cuantitativa | Claude Desktop respondió correctamente en las pruebas realizadas; en Android hubo respuestas tardías o inconsistentes. |
| Tiempo de reconexión | Sin medición cuantitativa | Se observaron interrupciones temporales en la recepción de distancia desde Android. |
| Disponibilidad y tasa de éxito | Sin medición cuantitativa | No se ejecutó una prueba estadística ni de carga; el control desde Android fue intermitente. |

No se dispone en esta documentación de valores numéricos del apartado §3.2 del enunciado, por lo que no se atribuyen umbrales de latencia, reconexión o disponibilidad que no hayan sido declarados y medidos. La validación descrita es funcional y exploratoria, no una certificación de rendimiento.

## 9. Configuración y ejecución

### 9.1. AWS IoT Core

1. Utilizar AWS IoT Core en `us-east-2` y obtener el endpoint ATS correspondiente a la cuenta de AWS.
2. Registrar el dispositivo `esp32-sis234` y crear identidades/certificados **independientes** para el ESP32, el servidor MCP y el móvil.
3. Asociar políticas con permisos mínimos para `iot:Connect`, `iot:Publish`, `iot:Subscribe` y `iot:Receive` según los tópicos necesarios.
4. Configurar el acceso a Device Shadow para los componentes que lo requieran.
5. Mantener certificados privados, claves y contraseñas **fuera del repositorio**.

### 9.2. Firmware ESP32

1. Abrir `firmware/` en **VS Code con PlatformIO**.
2. Crear los archivos locales de configuración a partir de las plantillas de `firmware/include/`:
   - `config.example.h` → `config.h`.
   - `aws_certificates.example.h` → `aws_certificates.h`.
3. Completar localmente Wi-Fi, endpoint AWS IoT, certificados y clave privada del dispositivo. **No publicar esos archivos.**
4. Conectar el HC-SR04 y los LEDs a los GPIO indicados en la sección 3.
5. Compilar y cargar el firmware en el ESP32; verificar la conexión MQTT y la publicación de distancias.

### 9.3. Servidor MCP

1. Entrar en `mcp-server/` y crear un entorno virtual de Python:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .
   ```

2. Crear el archivo local `.env` a partir de la plantilla `.env.example` y configurar endpoint, Client ID, tópicos y rutas a certificados del servidor MCP.
3. Ejecutar desde `mcp-server/`:

   ```powershell
   python smart-object.py
   ```

4. Configurar **Claude Desktop** para iniciar `smart-object.py` mediante el Python del entorno virtual, estableciendo `cwd` en la carpeta `mcp-server/`. Utilizar rutas locales para Python y el servidor; no publicar rutas con datos sensibles ni claves.
5. Reiniciar Claude Desktop y verificar que el servidor MCP figure como conectado y que las herramientas estén disponibles.

### 9.4. IoT MQTT Panel (Android)

1. Crear una conexión con el endpoint AWS IoT, puerto `8883`, protocolo `TCP-SSL` y Client ID `movil-sis234`.
2. Cargar el certificado CA de Amazon y el certificado del cliente móvil en formato PKCS#12 (`.p12`) protegido con contraseña. **No subir el `.p12` al repositorio.**
3. Crear un dashboard con un **Gauge** suscrito a `sis234/esp32/distancia` y JSONPath `$.cm`.
4. Crear tres **Switches** para publicar `on` y `off` en `sis234/esp32/comandos`, uno por LED. Deshabilitar el prefijo del dashboard para conservar el tópico exacto.
5. Verificar la lectura del sensor y la respuesta física de los LEDs.

## 10. Pruebas y limitaciones conocidas

- **Claude Desktop + MCP:** se verificó la consulta de distancia y el control físico de LEDs a través del servidor MCP y AWS IoT Core; las pruebas realizadas funcionaron correctamente.
- **IoT MQTT Panel:** se consiguió visualizar gráficamente la distancia y enviar comandos a los LEDs, pero el funcionamiento fue **intermitente**. En algunas ocasiones, el estado visual del interruptor no coincidía con el LED físico y era necesario volver a alternarlo. También se observaron interrupciones temporales en la actualización de la distancia.
- **Resultado final de las pruebas:** RF4 se visualizó en el Gauge y RF5 permitió accionar LEDs desde el teléfono, aunque con fallos intermitentes de actualización y sincronización. No se realizaron mediciones formales de latencia, disponibilidad o tasa de éxito.
