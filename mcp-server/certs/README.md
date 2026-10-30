# certs/ (local, NO se sube a Git)

Coloca aquí los archivos de la identidad **del servidor MCP** (no los de la ESP32):

| Archivo | Origen |
|---|---|
| `AmazonRootCA1.pem` | CA raíz de Amazon (descarga pública) |
| `mcp-certificate.pem.crt` | Certificado del servidor creado en AWS IoT |
| `mcp-private.pem.key` | Clave privada del servidor (solo se descarga una vez) |

Ver `docs/AWS_CONFIGURACION.md`. Todo el contenido de esta carpeta, salvo este README, está en `.gitignore`.
