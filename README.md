# Renpy UI Extractor

Extrae y traduce textos de UI, menús, screens y mensajes de teléfono que Zenpy NO traduce.

## Motores de traducción

| Comando | Motor | Calidad | Precio |
|--------|------|--------|--------|
| `--deeplx` | DeepLX | Excelente | Gratis |
| `--google` | Google | Regular | Gratis |
| `--deepl KEY` | DeepL | Mejor | Gratis (500k/mes) |

## Uso

```bash
# Extraer y traducir con DeepLX (gratis):
python renpy_ui_extractor.py "ruta/al/juego" "es" --deeplx

# Solo extraer (sin traducir):
python renpy_ui_extractor.py "ruta/al/juego" "es"
```

## Instalación

```bash
# No requiere instalación extra
python renpy_ui_extractor.py --help
```

## Características

- Extrae textbuttons, menús, screens
- Traduce automáticamente con DeepLX/Google/DeepL
- Genera archivo strings.rpy listo para Renpy
- Funciona junto con Zenpy (complementario)