---
name: Onboarding (CLI determinista)
description: CLI `cli.py` — extrae, parsea y genera el perfil del usuario en data/.
scope: GLOBAL
version: 3.0
---

# Onboarding (CLI `cli.py`)

Documentación del CLI `skills/onboarding/scripts/cli.py`. El agente conserva el **Paso 5 (verificación con el usuario)** como único paso conversacional.

## Comandos

Todos emiten JSON a stdout; exit `0` en `ok: true`, `1` en caso contrario.

```
python skills/onboarding/scripts/cli.py extract <pdf_path>
python skills/onboarding/scripts/cli.py parse <source> [--links URL ...]
python skills/onboarding/scripts/cli.py generate --fields-file <path> [--out-dir data] [--no-backup]
python skills/onboarding/scripts/cli.py full <pdf_path> [--fields-file <path>] [--out-dir data] [--no-backup]
```

| Comando | Qué hace |
|---|---|
| `extract` | Extrae texto + links de un PDF vía `pdf_parser.extract` (library import). |
| `parse` | Regex/heurísticas sobre texto (archivo, stdin `-`, o PDF). Devuelve `fields` + `missing`. |
| `generate` | Renderiza `perfil.md`, `correos.md`, `preferencias.md` desde `--fields-file` (JSON). |
| `full` | extract → parse → generate en una pasada. `--fields-file` aporta extras (preferencias, ejemplos de correos). |

## Flujo del agente

1. **Detección de estado:** si `data/perfil.md` existe y está completo, cargar silenciosamente. Si no, ejecutar onboarding.
2. **Recolección:** obtener el CV (PDF o texto pegado). Para PDF, ejecutar `full <pdf> --fields-file <extras.json>`. Para texto, `parse` → revisar `missing` → pedir campos faltantes al usuario → `generate`.
3. **Verificación (conversacional, obligatoria):** presentar el resumen de `fields` al usuario y pedir confirmación explícita antes de escribir. NUNCA escribir sin confirmación.
4. **Preferencias y correos:** recolectar sector, tono, idioma, borradores Gmail/Outlook y 2-3 ejemplos de correos. Pasarlos en el `--fields-file`.
5. **Persistencia:** el CLI escribe los tres archivos en `data/`.

## Campos esenciales (reportados en `missing`)

`nombre`, `linkedin`, `github`, `telefono`, `correo`.

## Plantillas

`skills/onboarding/templates/*.template.md` con placeholders `{{field}}`
(reemplazo por `str.replace`, sin Jinja2).

## Resolución de estado parcial

El archivo `data/.onboarding-state.md` se elimina en esta versión: cada
comando corre en segundos y reintentar es barato. Reintroducir como propuesta
separada si se reporta necesidad.

## Reglas de idioma

Todo texto dirigido al usuario en español neutral: sin voseo, sin jerga
regional. Tono profesional, cálido y directo.
