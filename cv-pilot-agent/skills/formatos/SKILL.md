---
name: Skill Formatos
description: Estructuras de salida obligatorias para análisis y contacto.
scope: STRUCTURAL_ONLY
---

# Skill: Formatos de Salida

## 1. Protocolo de Análisis (DB-Driven)
El agente DEBE seguir estos pasos antes de imprimir el reporte:
1. **Consulta:** Ejecutar `sqlite3 cv-pilot.db "SELECT * FROM jobs WHERE status = 'new';"` para identificar vacantes pendientes.
2. **Iteración:** Por cada vacante pendiente, ejecutar la fase de análisis.
3. **Persistencia:** Registrar el análisis en `analyses` y actualizar `jobs` a `status = 'analyzed'`.
4. **Impresión:** Usar los datos recuperados de la DB para completar el esquema a continuación.

## 2. Esquema de Análisis (Reporte Final)
### Análisis de la Vacante
🆔 ID: [analysis_id]
📅 Fecha: [created_at]
🔗 Fuente: [url]
💻 Empresa: [company] | Cargo: [position]
🚩Localidad: [location]
💲 Salario: [salary]
🎯 Porcentaje: [Calculado dinámicamente]

⚖️ **Comparativa Técnica:**
- Requisito: [Requisito de la oferta] | Análisis: [Evaluación basada en CV vs Vacante]

💡 **Observaciones y Riesgos:**
[Resumen obtenido de la columna 'summary']

✅ Veredicto: [verdict]
🌟 TL;DR: [Máximo 3 líneas]

## 3. Esquemas de Postulación
### A. Borrador Formal (Solo si detectas EMAIL)
- **Para:** [Email detectado]
- **Asunto:** [Asunto directo]
- **Cuerpo:** [Redacción basada en mimetismo, máx 500 caracteres]
- **Firma:** [Según `skills/contacto/SKILL.md`]
[📩 Abrir en tu gestor](mailto:[Email]?subject=[Asunto]&body=[Cuerpo])

### B. Carta de Presentación (Solo si es PORTAL)
Cuerpo para copiar y pegar:
[Texto optimizado para formulario web, sin asuntos ni firmas]

## Instrucciones para el Agente
- **Cero citas:** No incluyas marcadores de origen (ej. [cite: 1]) en el texto final.
- **Formato estricto:** Si la oferta es portal, NO generes el formato "Borrador Formal". Entrega exclusivamente la "Carta de Presentación".
