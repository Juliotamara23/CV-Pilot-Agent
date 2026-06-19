# Escenario 09: Flujo Multi-Scraper — Computrabajo

**Entrada del Usuario:**
1. "Busca 1 trabajo de desarrollador en Computrabajo para Medellín."
2. "Analízalo y muéstrame el reporte."

**Flujo Esperado:**
1. **Detección de plataforma:** Agente detecta "Computrabajo" en el mensaje.
2. **Parámetros:** position=desarrollador, location=Medellín, count=1, platform=computrabajo.
3. **Costo:** Agente consulta `apify actors info shahidirfan/computrabajo-jobs-scraper --json` para obtener `eventPriceUsd` + costo de arranque.
4. **Construcción de URL:** Agente genera URL con subdominio `co.computrabajo.com`.
5. **Ejecución:** `apify call shahidirfan/computrabajo-jobs-scraper` (simulado en test con mock data).
6. **Validación:** Resultados se validan contra el término de búsqueda.
7. **Normalización:** Campos de Computrabajo (`title`→position, `companyName`→company) se mapean a DB.
8. **Persistencia:** Jobs insertados con `source='apify-computrabajo'`.
9. **Análisis:** Agente compara contra CV real y persiste en `analyses`.
10. **Reporte:** Agente muestra reporte con Formatos SKILL, indicando plataforma de origen.

**Verificaciones:**
- Source en DB es `apify-computrabajo`.
- El costo informado incluye arranque + resultados.
- La URL de búsqueda usa el subdominio correcto según el país.
- El reporte muestra el origen de la plataforma.
