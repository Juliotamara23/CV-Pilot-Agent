---
name: Skill Apify Scraper
description: Interfaz para ejecutar scrapers de Apify y recuperar resultados.
scope: SOURCING_PHASE
---

# Skill: Apify Scraper

## 1. Esquema de Entrada (JSON Schema)
Cuando el usuario confirme la búsqueda, el agente DEBE construir el JSON basándose estrictamente en esta estructura (los valores de 'maxItemsPerSearch' deben ser definidos por el usuario):

```json
{
  "position": "[CARGO_SOLICITADO]",
  "country": "[PAIS_SOLICITADO]",
  "location": "[UBICACION_SOLICITADA]",
  "maxItemsPerSearch": [CANTIDAD_DEFINIDA_POR_USUARIO],
  "parseCompanyDetails": true,
  "saveOnlyUniqueItems": true,
  "followApplyRedirects": false
}
```

## 2. Protocolo de Gestión de Costos
Antes de ejecutar la búsqueda, el agente DEBE:
1. Obtener información del actor: `apify actors info misceres/indeed-scraper`.
2. Identificar el costo por ítem ("Pricing information").
3. Calcular costo: `CANTIDAD_DEFINIDA * Costo por Job listing`.
4. Informar: "Para buscar [CANTIDAD] empleos, el costo estimado es de [Costo calculado] USD. ¿Confirmas la ejecución?".

## 3. Protocolo de Ejecución Técnica (One-Shot Sync)
1. **Validación:** Ejecutar `apify --version`. Si falla, avisar al usuario.
2. **Lanzamiento y Recuperación:** Ejecutar:
   `apify call misceres/indeed-scraper -i '<json_input>' --output-dataset --json --silent`
   - La flag `--output-dataset` bloquea la ejecución hasta finalizar el proceso y descarga los resultados automáticamente.
   - La flag `--json` garantiza el formato parseable para el agente.

## 4. Instrucciones para el Agente (Naturalización)
- **Estado de Espera:** Informar: "Iniciando búsqueda automatizada. Esto tardará unos minutos, te avisaré al terminar."
- **Transparencia:** El usuario NO debe ver código, JSON o tecnicismos. Solo lenguaje natural.
- **Integridad:** Validar que el dataset tenga campos: `title`, `companyName`, `location`, `description`. Si está vacío o corrupto, abortar.
- **Manejo de Errores:**
    - Fallo de Auth: "No tengo permiso para ejecutar el scraper. Ejecuta 'apify login' en tu terminal."
    - Sin resultados: "No encontré vacantes con ese cargo. ¿Quieres intentar con una palabra clave diferente?"
