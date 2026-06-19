---
name: Skill Apify Scraper
description: Ejecución de scraping multi-plataforma mediante CLI de Apify.
scope: SOURCING_PHASE
version: 2.0
---

# Skill: Apify Scraper (Multi-Plataforma)

## 0. Plataformas Disponibles

| Plataforma | Archivo | Actor | $/resultado (ref) |
|-----------|---------|-------|-------------------|
| Indeed | `platforms/indeed.md` | `misceres/indeed-scraper` | $0.003 |
| LinkedIn | `platforms/linkedin.md` | `curious_coder/linkedin-jobs-scraper` | $0.001 |
| Computrabajo | `platforms/computrabajo.md` | `shahidirfan/computrabajo-jobs-scraper` | $0.00199 |

## 1. Selección de Plataforma

Antes de cualquier ejecución, el agente DEBE determinar la plataforma:

1. **Detectar en el mensaje del usuario:** ¿mencionó "LinkedIn", "Computrabajo", "Indeed"?
   - Si sí → usar esa plataforma.
2. **Si no mencionó ninguna:**
   - Preguntar: "¿Dónde quieres buscar? Indeed ($0.003/job), LinkedIn ($0.001/job) o Computrabajo ($0.00199/job)."
   - Si el usuario no elige explícitamente, usar Indeed como default.
   - Si el usuario quiere múltiples plataformas, ejecutar secuencialmente y sumar costos.
3. **Cargar el platform SKILL** correspondiente (`platforms/<nombre>.md`) antes de construir el input JSON.

## 2. Resolución de Parámetros

Antes de ejecutar, el agente DEBE tener estos parámetros definidos. Si falta alguno, preguntar al usuario:

| Parámetro | Si falta... | Default |
|---|---|---|
| position | Preguntar al usuario | — (obligatorio) |
| maxItemsPerSearch | Preguntar cantidad deseada | 5 |
| location | Preguntar ubicación | "Remote" |
| country | Inferir del location o preguntar | "CO" por defecto |

### Advertencia: position genérico

Si el `position` es una sola palabra (ej: "Desarrollador", "Developer", "Ingeniero"), Indeed y otras plataformas pueden devolver resultados poco relevantes. El agente DEBE sugerir refinarlo:

> "El término '[position]' es genérico. Las plataformas pueden devolver resultados variados. Sugiero refinarlo, por ejemplo: 'Desarrollador de Software', 'Software Developer', 'Full Stack Developer'. ¿Quieres ajustarlo o procedo con el término actual?"

Si el usuario decide no refinar, proceder igual pero anotar que los resultados pueden ser imprecisos.

## 3. Protocolo de Extracción de Parámetros

El agente DEBE extraer del prompt del usuario:
- **platform**: (detectado en paso 1)
- **position**: (Ej: "Software Engineer", "Backend Developer")
- **country**: (Ej: "CO", "US")
- **location**: (Ej: "Medellín", "Remote")
- **maxItemsPerSearch**: (Solicitado por el usuario, máximo 100)

## 4. Cálculo de Costo (TIEMPO REAL)

El agente NUNCA debe hardcodear el precio. Antes de cotizar al usuario:

1. Ejecutar: `apify actors info <actor> --json`
2. Extraer `currentPricingInfo.pricingPerEvent.actorChargeEvents."apify-default-dataset-item".eventPriceUsd`
3. Extraer `currentPricingInfo.pricingPerEvent.actorChargeEvents."apify-actor-start".eventPriceUsd` (si existe)
4. Calcular: `costo_total = (count × precio_por_resultado) + costo_arranque`
5. Informar al usuario: "La búsqueda de [X] empleos en [Plataforma] costará aproximadamente [Y] USD. ¿Confirmas?"

## 5. Ejecución Técnica

1. **Validar entorno:** `apify --version`. Si falla, abortar y notificar.
2. **Verificar token:** `$env:APIFY_TOKEN` o `auth.json`. Si no, notificar.
3. **Construir input JSON** según el platform SKILL cargado.
4. **Lanzar ejecución:**
   ```bash
   echo '<json>' | apify call <actor> --silent --output-dataset
   ```
5. **Recuperar resultados:** Extraer `defaultDatasetId` y obtener items:
   ```bash
   curl -s -H "Authorization: Bearer $env:APIFY_TOKEN" "https://api.apify.com/v2/datasets/<DATASET_ID>/items"
   ```
   Si el dataset está vacío, informar que no se encontraron vacantes.

## 6. Validación de Relevancia (Post-Scrape)

Después de recuperar los resultados, validar que los títulos coinciden con la intención de búsqueda:

1. **Comparar positionName/title vs el position buscado:** ¿El título contiene una variante del término o sus sinónimos?
   - Si el usuario pidió "Desarrollador" y el resultado dice "Desarrollador de Software" → **válido**.
   - Si dice "GESTOR DE CLIENTES" → **no válido**.

2. **Si todos los resultados son no válidos:**
   > "El scraper devolvió [N] resultados, pero ninguno coincide con el perfil de '[position]'. Por ejemplo, encontré '[positionName real]'. ¿Quieres refinar la búsqueda con términos más específicos como '[sugerencia 1]', '[sugerencia 2]'?"

3. **Si hay mezcla:** Descartar los no válidos en silencio, procesar solo los válidos.

4. **Si todos son válidos:** Proceder normalmente.

## 7. Persistencia

Mapear campos según el platform SKILL → normalizar según Database SKILL → insertar con source según plataforma:
- `apify-indeed`
- `apify-linkedin`
- `apify-computrabajo`

## 8. Manejo de Errores

- CLI no instalado → notificar al usuario.
- Actor falla (status != SUCCEEDED) → reintentar una vez; si falla de nuevo, abortar.
- Dataset vacío → informar que no se encontraron vacantes.
- Token faltante → notificar al usuario que configure APIFY_TOKEN.
- Actor no tiene `currentPricingInfo` → abortar y notificar (posible error de autenticación).

## 9. Ejemplos de Comportamiento

### Con plataforma explícita
- **Usuario:** "Busca 3 trabajos de React en LinkedIn para Colombia"
- **Agente:** (Detecta LinkedIn, consulta precio real del actor) "Buscando 3 vacantes de React en LinkedIn Colombia. Costo estimado: $0.003 USD. ¿Confirmas?"
- **Usuario:** "Sí"
- **Agente:** (Ejecuta, recupera 3 vacantes) "Aquí están los resultados..."

### Sin plataforma (default + pregunta)
- **Usuario:** "Busca 5 trabajos de backend en Medellín"
- **Agente:** "¿En qué plataforma? Indeed ($0.003/job), LinkedIn ($0.001/job) o Computrabajo ($0.00199/job)."
- **Usuario:** "LinkedIn"
- **Agente:** (Consulta precio real, calcula, confirma, ejecuta)
