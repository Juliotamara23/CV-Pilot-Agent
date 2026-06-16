---
name: Skill Apify Scraper
description: Interfaz para ejecutar scrapers de Apify y recuperar resultados.
scope: SOURCING_PHASE
---

# Skill: Apify Scraper

## 1. Protocolo de Inferencia (Input Architect)
El agente DEBE construir el JSON de entrada aplicando lógica de inferencia antes de solicitar información al usuario:
- **Cargo:** Extraer del prompt o inferir del perfil profesional definido en `resources/identidad.md`.
- **Ubicación:** Extraer del prompt o inferir de la ubicación del usuario en `resources/identidad.md`.
- **Cantidad:** Extraer explícitamente del prompt. Si no se especifica, preguntar al usuario.
- **JSON Structure:**
```json
{
  "position": "[CARGO_INFERIDO]",
  "country": "[PAIS_INFERIDO]",
  "location": "[UBICACION_INFERIDA]",
  "maxItemsPerSearch": [CANTIDAD_INFERIDA],
  "parseCompanyDetails": true,
  "saveOnlyUniqueItems": true,
  "followApplyRedirects": false
}
```

## 2. Gestión de Costos
Antes de ejecutar `apify call`, el agente DEBE:
1. Obtener información del actor: `apify actors info misceres/indeed-scraper`.
2. Calcular costo: `CANTIDAD_INFERIDA * Costo por Job listing`.
3. Informar: "He configurado la búsqueda para [CARGO] en [UBICACION]. Buscaré [CANTIDAD] resultados con un costo estimado de [COSTO] USD. ¿Confirmas la ejecución?".

## 3. Ejecución Técnica (Bash/CLI)
1. **Validación:** Ejecutar `apify --version`. Si falla, avisar al usuario.
2. **Lanzamiento:** Ejecutar `apify call misceres/indeed-scraper -i '<json_input>' --output-dataset --json --silent`.
3. **Monitorización:** Capturar `runId`, monitorear hasta `SUCCEEDED`.
4. **Recuperación:** Ejecutar `apify dataset get <dataset_id> --format json`.

## 4. Instrucciones para el Agente (Naturalización)
- **Estado de Espera:** Informar: "Iniciando búsqueda automatizada. Esto tardará unos minutos, te avisaré al terminar."
- **Transparencia:** El usuario NO debe ver código, JSON o tecnicismos.
- **Integridad:** Validar campos `title`, `companyName`, `location`, `description`. Si está vacío o corrupto, abortar.
- **Manejo de Errores:** Fallo de Auth (ejecutar `apify login`) o Sin resultados (sugerir ajustar términos).
