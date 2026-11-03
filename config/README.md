# Configuraciones

| Archivo | Uso |
|---|---|
| `claude_desktop_config.example.json` | Registro del servidor MCP en Claude Desktop. Cambia la ruta absoluta. Si falla, pon la ruta completa de `uv` (`where uv`) en `command`. En Windows el archivo real es `%APPDATA%\Claude\claude_desktop_config.json`. |
| `../firmware/include/config.example.h` | Plantilla del ESP32 → copiar como `config.h` |
| `../firmware/include/aws_certificates.example.h` | Plantilla de certificados del ESP32 → copiar como `aws_certificates.h` |
| `../mcp-server/.env.example` | Plantilla del servidor MCP → copiar como `.env` |
| `policies/` | Políticas AWS de referencia (ESP32, servidor MCP, app móvil) |

Las credenciales y los archivos `.pem`/`.key` reales están en `.gitignore`.
