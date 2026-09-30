---
name: onboarding
description: "CLI `cli.py` — extrae, parsea y genera el perfil del usuario en data/."
scope: GLOBAL
version: 3.0
required_in_flujo: true
---

# Onboarding (CLI `cli.py`)

Documentación del CLI `skills/onboarding/scripts/cli.py`. El agente conserva el paso de **verificación con el usuario** como único paso conversacional.

## Flujo del agente

1. **Detección de estado:** si `data/perfil.json` existe y está completo, cargar silenciosamente. Si no, ejecutar onboarding.
2. **Recolección:** obtener el CV (PDF o texto pegado). Para PDF, ejecutar `full <pdf> --fields-file <extras.json>`. Para texto, `parse` → revisar `missing` → pedir campos faltantes al usuario → `generate`.
3. **Verificación (conversacional, obligatoria):** presentar el resumen de `fields` al usuario y pedir confirmación explícita antes de escribir. NUNCA escribir sin confirmación.
4. **Preferencias y correos:** recolectar sector, tono, idioma, borradores Gmail/Outlook y 2-3 ejemplos de correos. Pasarlos en el `--fields-file`.
5. **Persistencia:** el CLI escribe los tres archivos (`perfil.json`, `correos.md`, `preferencias.json`) en `data/`.

## Comandos

`extract <pdf>`, `parse <source> [--links]`, `generate --fields-file <path>`, `full <pdf>`. Todos emiten JSON a stdout; exit `0` en `ok: true`, `1` en caso contrario. Para flags, defaults y comportamiento exacto de cada comando, ejecuta `cli.py <command> --help`.

Campos esenciales (reportados en `missing`): `nombre`, `linkedin`, `github`, `telefono`, `correo`.

## Reglas de idioma

Todo texto dirigido al usuario en español neutral: sin voseo, sin jerga regional. Tono profesional, cálido y directo.
