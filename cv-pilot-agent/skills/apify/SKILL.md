---
name: Skill Apify Scraper
description: Interfaz para ejecutar scrapers de Apify y recuperar resultados.
scope: SOURCING_PHASE
---

# Skill: Apify Scraper

## Esquema de Entrada (JSON Schema)
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

## Gobernanza y Control de Costos
Antes de ejecutar `apify call`, el agente DEBE:
1. **Verificación de Actor:** Obtener información con `apify actors info misceres/indeed-scraper` para conocer el costo real por ítem.
2. **Límite de seguridad:** Nunca ejecutar una búsqueda > 100 resultados sin validación explícita.
3. **Concurrencia:** Ejecutar scrapers de forma secuencial. Nunca disparar procesos paralelos.
4. **Validación previa:** Calcular costo (Resultados * Costo por ítem) e informar: "Para buscar [CANTIDAD] empleos, el costo estimado es de [Costo calculado] USD. ¿Confirmas la ejecución?".

## Protocolo de Ejecución Técnica (Bash/CLI)
1. **Validación:** Ejecutar `apify --version`. Si falla, avisar al usuario.
2. **Lanzamiento:** Construir JSON dinámicamente y ejecutar: 
   `apify call misceres/indeed-scraper -i '<json_input>' --output-dataset`
3. **Monitorización:** Capturar el `runId` del output y verificar estado hasta `SUCCEEDED`.
4. **Recuperación:** Ejecutar `apify dataset get <dataset_id> --format json`.

## Instrucciones para el Agente (Naturalización)
- **Estado de Espera:** Durante la ejecución, informar: "Iniciando búsqueda automatizada. Esto tardará unos minutos, te avisaré al terminar."
- **Transparencia:** El usuario NO debe ver código, JSON o tecnicismos. Solo lenguaje natural.
- **Integridad:** Validar que el dataset tenga campos: `title`, `companyName`, `location`, `description`. Si está vacío, abortar.
- **Manejo de Errores:**
    - Fallo de Auth: "No tengo permiso para usar Apify. Ejecuta 'apify login' en tu terminal."
    - Sin resultados: "No encontré vacantes con ese cargo. ¿Quieres intentar con una palabra clave diferente?"
