# Renpy UI Extractor

Extrae y traduce textos de UI, menús, screens y mensajes de teléfono que Zenpy NO traduce.

## Interfaz GUI (Recomendado)

```bash
python renpy_ui_extractor.py --gui
```

La GUI te permite:
- Seleccionar carpeta del juego con un clic
- Elegir idioma objetivo
- Elegir motor de traducción
- Ver progreso en tiempo real

## Línea de comandos

```bash
# Extraer y traducir con DeepLX (gratis):
python renpy_ui_extractor.py "ruta/al/juego" "es" --deeplx

# Con endpoint personalizado (DeepLX local):
python renpy_ui_extractor.py "ruta/al/juego" "es" --deeplx --endpoint http://localhost:1188/translate

# Solo extraer (sin traducir):
python renpy_ui_extractor.py "ruta/al/juego" "es"
```

## Motores de traducción

| Comando | Motor | Calidad | Precio |
|--------|------|--------|--------|
| `--deeplx` | DeepLX | Excelente | Gratis |
| `--google` | Google | Regular | Gratis |
| `--deepl KEY` | DeepL | Mejor | Gratis (500k/mes) |

Por defecto usa `http://localhost:1188/translate` para DeepLX.

## Instalación

```bash
# No requiere instalación extra
python renpy_ui_extractor.py --help
```

## Características

- Interfaz GUI con un clic
- Extrae textbuttons, menús, screens
- Traduce automáticamente con DeepLX/Google/DeepL
- Genera archivo strings.rpy listo para Renpy
- Funciona junto con Zenpy (complementario)