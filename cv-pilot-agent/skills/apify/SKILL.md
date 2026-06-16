---
name: Skill Apify Scraper
description: Ejecución de scraping mediante CLI de Apify.
scope: SOURCING_PHASE
---

# Skill: Apify Scraper

## 1. Protocolo de Extracción de Parámetros
Para ejecutar `misceres/indeed-scraper`, el agente DEBE extraer los siguientes parámetros del prompt o CV del usuario:
- **position**: (Ej: "Software Engineer", "Backend Developer")
- **country**: (Ej: "CO", "US")
- **location**: (Ej: "Medellín", "Remote")
- **maxItemsPerSearch**: (Solicitado por el usuario, máximo 100)

## 2. Construcción de Input (JSON)
El agente debe generar este JSON estrictamente:
```json
{
  "position": "[EXTRACTED_POSITION]",
  "country": "[EXTRACTED_COUNTRY]",
  "location": "[EXTRACTED_LOCATION]",
  "maxItemsPerSearch": [INT_NUMBER],
  "parseCompanyDetails": true,
  "saveOnlyUniqueItems": true,
  "followApplyRedirects": false
}
```

## 3. Ejecución Técnica (Bash)
1. **Validar entorno:** `apify --version`
2. **Lanzamiento:** `apify call misceres/indeed-scraper -i '<json>' --output-dataset --json --silent`
3. **Recuperación:** La flag `--output-dataset` descarga el JSON automáticamente.

## 4. Instrucciones de Operación
- **Costo:** Informar: "La búsqueda estimada de [X] empleos costará [Y] USD. ¿Confirmas?"
- **Naturalización:** NUNCA mostrar el JSON al usuario. Usar: "Buscando [Cargo] en [Ubicación]...".
- **Integridad:** Si el JSON resultante no tiene `title`, `companyName` o `description`, abortar y pedir al usuario ajustar parámetros.
