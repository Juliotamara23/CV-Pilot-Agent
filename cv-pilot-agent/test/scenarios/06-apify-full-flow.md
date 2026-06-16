# Escenario 06: Flujo Completo Apify + Persistencia

**Input:**
1. "Hola."
2. "Búscame 1 oferta de trabajo en Medellín para desarrollador junior."
3. "Me guardaste la información en la DB? ¿Me puedes mostrar cuál era el trabajo, por favor?"

**Entorno de Prueba:**
- Mapeo: `resources/` -> `cv-test/`.
- Scraper: `misceres/indeed-scraper`.

**Expectativas:**
- Agente realiza Onboarding y VSI correctamente.
- Agente calcula costos de Apify y pide confirmación.
- Agente inserta el resultado en `cv-pilot.db` (tabla `jobs`).
- Agente responde al usuario confirmando el registro sin revelar SQL/técnicos.
