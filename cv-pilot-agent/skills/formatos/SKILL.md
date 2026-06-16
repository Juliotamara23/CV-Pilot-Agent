---
name: Skill Formatos
description: Estructuras de salida obligatorias para análisis y contacto.
scope: STRUCTURAL_ONLY
---

# Skill: Formatos de Salida

## Esquema de Análisis
El agente DEBE seguir esta estructura estrictamente:

### Análisis de la Vacante
🆔 ID: [YYYYMMDD]-[Incremental]-[Porcentaje]
📅 Fecha: [Actual]
🔗 Fuente: [URL detectada del texto | "Origen: Texto manual"]
💻 Empresa: [Nombre] | Cargo: [Nombre]
🚩Localidad: [Localidad]
💲 Salario: [Salario]
🎯 Porcentaje: [X%]

⚖️ **Comparativa Técnica:**
- Requisito: [Requisito de la oferta] | Análisis: [Evaluación basada en CV vs Vacante]

💡 **Observaciones y Riesgos:**
[Análisis profundo: curva de aprendizaje, stack, impacto de brechas]

✅ Veredicto: [Apto | Apto con reservas | No apto]
🌟 TL;DR: [Máximo 3 líneas]

## Esquemas de Postulación

### A. Borrador Formal (Solo si detectas EMAIL)
Este es el borrador sugerido:
- **Para:** [Email detectado]
- **Asunto:** [Asunto directo]
- **Cuerpo:** [Texto basado en mimetismo, máx 500 caracteres]
- **Firma:** [Según `skills/contacto/SKILL.md`]

Enlace rápido: [📩 Abrir en tu gestor](mailto:[Email]?subject=[Asunto]&body=[Cuerpo])

### B. Carta de Presentación (Solo si es PORTAL)
Cuerpo para copiar y pegar:
[Texto optimizado para formulario web, sin asuntos ni firmas]

## Instrucciones para el Agente
- **Cero citas:** No incluyas marcadores de origen (ej. [cite: 1]) en el texto final.
- **Formato estricto:** Si la oferta es portal, NO generes el formato "Borrador Formal". Entrega exclusivamente la "Carta de Presentación".
