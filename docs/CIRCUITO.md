# Circuito

## Pines (montaje real del grupo)

| Componente | GPIO ESP32 | Notas |
|---|---|---|
| HC-SR04 TRIG | 27 | |
| HC-SR04 ECHO | 26 | **a través del divisor de voltaje** |
| LED rojo | 14 | resistencia 220 Ω a GND |
| LED verde | 13 | resistencia 220 Ω a GND |
| LED amarillo | 12 | ver advertencia GPIO12 |
| HC-SR04 VCC | VIN (5 V) | |
| GND (sensor, LEDs) | GND | todo comparte masa |

El diseño inicial del enunciado era TRIG 5, ECHO 18, LEDs 25/26/27. **Los pines son configurables** en `firmware/include/config.h` (`PIN_TRIG`, `PIN_ECHO`, `PIN_LED_*`); no hace falta recablear si usas los de arriba.

## Divisor de voltaje para ECHO

El HC-SR04 se alimenta con 5 V y su pin ECHO entrega ~5 V. Los GPIO de la ESP32 toleran 3,3 V: sin protección se puede dañar el pin o el chip.

```
ECHO ──[ R1 = 1 kΩ ]──┬── GPIO26 (ESP32)
                      │
                  [ R2 = 2 kΩ ]
                      │
                     GND
```
`Vsalida = 5 V × 2k / (1k + 2k) ≈ 3,3 V`. Cualquier relación 1:2 sirve (p. ej. 2,2 kΩ + 4,7 kΩ). TRIG no necesita divisor (entra 3,3 V al sensor, que lo reconoce como alto).

## LEDs

```
GPIO ──[ 220 Ω ]──►|── GND        (ánodo/patilla larga hacia la resistencia)
```
Con esta conexión `LED_ACTIVE_LOW` queda en `0`. Si los conectaste entre 3,3 V y el GPIO, usa `LED_ACTIVE_LOW 1`. Sin resistencia el LED y el pin pueden dañarse.

## Advertencia: GPIO12
GPIO12 es un pin de arranque del ESP32: si está en alto al encender, algunas placas no inician (errores tipo `invalid header` o reinicios continuos). Con LED + resistencia a GND queda en bajo y no suele haber problema. Si el ESP32 no arranca con el LED amarillo conectado, desconéctalo para arrancar o muévelo a otro GPIO libre (p. ej. 25 o 33) y cambia `PIN_LED_YELLOW`.

## Verificación antes de energizar
- [ ] ECHO pasa por el divisor
- [ ] Todos los GND unidos
- [ ] Cada LED con su resistencia
- [ ] VCC del sensor en 5 V (VIN), no en 3,3 V

## Rango de trabajo
El sensor mide de ~2 cm a ~400 cm. El firmware descarta lecturas fuera de `SENSOR_MIN_CM`..`SENSOR_MAX_CM` y publica la **mediana de 3 lecturas**. Mide con una cinta métrica y **declara tu rango útil real** (p. ej. 5–150 cm) en el README.
