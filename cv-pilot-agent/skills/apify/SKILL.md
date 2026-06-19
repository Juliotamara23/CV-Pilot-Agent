---
name: Skill Apify Scraper
description: Ejecución de scraping mediante CLI de Apify.
scope: SOURCING_PHASE
---

# Skill: Apify Scraper

## 0. Resolución de Parámetros
Antes de ejecutar, el agente DEBE tener estos parámetros definidos. Si falta alguno, preguntar al usuario:

| Parámetro | Si falta... | Default |
|---|---|---|
| position | Preguntar al usuario | — (obligatorio) |
| maxItemsPerSearch | Preguntar cantidad deseada | 5 |
| location | Preguntar ubicación | "Remote" |
| country | Inferir del location o preguntar | "CO" por defecto |

Si el usuario no responde un parámetro después de preguntar, usar el default indicado.

### Advertencia: position genérico
Si el `position` es una sola palabra (ej: "Desarrollador", "Developer", "Ingeniero"), Indeed puede devolver resultados poco relevantes porque busca esa palabra en cualquier parte de la oferta, no solo en el título. El agente DEBE sugerir refinarlo antes de ejecutar:

> "El término '[position]' es genérico. Indeed puede devolver resultados variados que solo mencionen esa palabra en la descripción. Sugiero refinarlo, por ejemplo: 'Desarrollador de Software', 'Software Developer', 'Full Stack Developer'. ¿Querés ajustarlo o procedo con el término actual?"

Si el usuario decide no refinar, proceder igual pero anotar que los resultados pueden ser imprecisos.

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

## 6. Validación de Relevancia (Post-Scrape)
Después de recuperar los resultados, el agente DEBE validar que los `positionName` coinciden con la intención de búsqueda:

1. **Comparar positionName vs el position buscado:** ¿El título del puesto contiene una variante del término buscado o sus sinónimos?
   - Si el usuario pidió "Desarrollador" y el resultado dice "Desarrollador de Software" → **válido**.
   - Si el resultado dice "GESTOR DE CLIENTES" → **no válido**.

2. **Si todos los resultados son no válidos:**
   > "El scraper devolvió [N] resultados, pero ninguno coincide con el perfil de '[position]' que buscamos. Por ejemplo, encontré '[positionName real]' que es un rol diferente. ¿Querés que refine la búsqueda con términos más específicos como '[sugerencia 1]', '[sugerencia 2]'?"

3. **Si hay mezcla de válidos y no válidos:** Descartar los no válidos en silencio, procesar solo los válidos, y en la nota del análisis informar cuántos se descartaron.

4. **Si todos son válidos:** Proceder normalmente.
