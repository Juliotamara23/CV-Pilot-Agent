# Escenario 06: Flujo Completo Apify + Persistencia + Análisis

**Entrada del Usuario:**
1. "Hola."
2. "Búscame 1 oferta de trabajo en Medellín para desarrollador junior."
3. "Me guardaste la información en la DB? ¿Me puedes mostrar cuál era el trabajo, por favor?"

**Flujo Esperado:**
1. **Saludo:** Agente se presenta con propósito senior + solicita CV (Paso 0).
2. **Validación CV:** Agente valida la información.
3. **Búsqueda:** 
   - Usuario pide búsqueda para "Desarrollador Junior" en "Medellín".
   - Agente ejecuta `scripts/init.py` -> "DB Ready".
   - Agente calcula costos y solicita confirmación.
   - Agente ejecuta `skills/apify/SKILL.md` (apify call).
   - Agente registra en DB.
4. **Análisis:**
   - Agente detecta trabajos nuevos en status 'new'.
   - Agente invoca `skills/formatos/SKILL.md` para generar el análisis detallado por vacante.
   - Agente guarda el análisis en tabla `analyses`.
5. **Consulta DB:**
   - Usuario pide ver el trabajo guardado.
   - Agente invoca `skills/database/SKILL.md` (SELECT query).
   - Agente responde con los detalles (Empresa, Cargo, Ubicación, URL) sin revelar datos técnicos (SQL/Protocolos).
