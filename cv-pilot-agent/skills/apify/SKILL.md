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

> Opcional: `startUrls` permite scrapear URLs directas de Indeed (búsquedas guardadas, company jobs, etc.). No usar cuando se busca por keywords.

## 3. Ejecución Técnica (Bash)
1. **Validar entorno:** `apify --version`. Si falla, abortar y notificar al usuario.
2. **Verificar token:** `$env:APIFY_TOKEN` debe estar configurado. Si no, notificar al usuario.
3. **Lanzar ejecución:**
   ```bash
   echo '<json>' | apify call misceres/indeed-scraper --silent --output-dataset
   ```
   Alternativa: `apify call misceres/indeed-scraper -i '<json>' --silent --output-dataset`
4. **Recuperar resultados:** Del output del comando extraer `defaultDatasetId` y obtener los items:
   ```bash
   curl -s -H "Authorization: Bearer $env:APIFY_TOKEN" `
     "https://api.apify.com/v2/datasets/<DATASET_ID>/items"
   ```
   Si el dataset está vacío o el request falla, notificar que no se encontraron vacantes.

## 4. Ejemplos de Comportamiento (Few-Shot)
### Ejemplo Correcto (Precisión)
- **Usuario:** "Busca 2 trabajos para Medellín."
- **Agente:** (Calcula costo para 2) "He configurado la búsqueda para Medellín. El costo estimado es de 0.006 USD para 2 empleos. ¿Confirmas la ejecución?"
- **Usuario:** "Sí"
- **Agente:** (Ejecuta, recupera 2 vacantes) "Aquí tienes tu lista de trabajos: [Trabajo 1, Trabajo 2]."

### Ejemplo Incorrecto (No seguir instrucciones)
- **Usuario:** "Busca 2 trabajos para Medellín."
- **Agente:** (Ignorar cantidad de empleos y ubicación) "Aquí tienes tu lista de trabajos: [Lista de 10 trabajos]."
- **Error:** El agente ignoró la cantidad solicitada, impactando el presupuesto.

## 5. Operación y Costo
- **Costo:** Precio base: $3.00 / 1,000 listings. Calcular: `Y = X * 0.003` USD. Informar: "La búsqueda de [X] empleos costará estimadamente [Y] USD. ¿Confirmas?"
- **Naturalización:** NUNCA mostrar el JSON al usuario. Usar: "Buscando [Cargo] en [Ubicación]...".
- **Validación de integridad:** Cada item del dataset debe tener `positionName`, `company` y `description`. Si algún item carece de estos campos, abortar y pedir al usuario revisar parámetros.
- **Manejo de errores:**
  - CLI no instalado → notificar al usuario.
  - Actor falla (status != SUCCEEDED) → reintentar una vez; si falla de nuevo, abortar y notificar.
  - Dataset vacío → informar que no se encontraron vacantes para esa búsqueda.
  - Token faltante o inválido → notificar al usuario que configure APIFY_TOKEN.
