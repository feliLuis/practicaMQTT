/**
 * @file aws_certificates.example.h
 * @brief Plantilla de certificados. Copiar como "aws_certificates.h".
 *
 * "aws_certificates.h" está en .gitignore. Contiene la CLAVE PRIVADA de la ESP32:
 * no la subas a Git, no la compartas y no la pegues en chats.
 *
 * Pega el contenido COMPLETO de cada archivo (incluidas las líneas BEGIN/END)
 * entre R"EOF( y )EOF". No dejes espacios antes de las líneas -----BEGIN.
 */
#pragma once

// AmazonRootCA1.pem
static const char AWS_CERT_CA[] = R"EOF(
-----BEGIN CERTIFICATE-----
PEGA_AQUI_AmazonRootCA1.pem
-----END CERTIFICATE-----
)EOF";

// certificate.pem (certificado del dispositivo; en AWS termina en -certificate.pem.crt)
static const char AWS_CERT_CRT[] = R"EOF(
-----BEGIN CERTIFICATE-----
PEGA_AQUI_certificate.pem
-----END CERTIFICATE-----
)EOF";

// private.pem.key (clave privada del dispositivo)
static const char AWS_CERT_PRIVATE_KEY[] = R"EOF(
-----BEGIN RSA PRIVATE KEY-----
PEGA_AQUI_private.pem.key
-----END RSA PRIVATE KEY-----
)EOF";
