# Escenario 08: Flujo Multi-Scraper — LinkedIn

**Entrada del Usuario:**
1. "Busca 1 trabajo de React en LinkedIn para Colombia."
2. "Analízalo y muéstrame el reporte."

**Flujo Esperado:**
1. **Detección de plataforma:** Agente detecta "LinkedIn" en el mensaje.
2. **Parámetros:** position=React, location=Colombia, count=1, platform=linkedin.
3. **Costo:** Agente consulta `apify actors info curious_coder/linkedin-jobs-scraper --json` para obtener `eventPriceUsd` real.
4. **Construcción de URL:** Agente genera la URL de búsqueda de LinkedIn automáticamente.
5. **Ejecución:** `apify call curious_coder/linkedin-jobs-scraper` (simulado en test con mock data).
6. **Validación:** Resultados se validan contra el término de búsqueda.
7. **Normalización:** Campos de LinkedIn (`title`→position, `companyName`→company) se mapean a DB.
8. **Persistencia:** Jobs insertados con `source='apify-linkedin'`.
9. **Análisis:** Agente compara contra CV real y persiste en `analyses`.
10. **Reporte:** Agente muestra reporte con Formatos SKILL, indicando plataforma de origen.

**Verificaciones:**
- Source en DB es `apify-linkedin` (no `apify` genérico).
- Campo `title` de LinkedIn se mapea correctamente a `position` en DB.
- El reporte muestra el origen de la plataforma.
