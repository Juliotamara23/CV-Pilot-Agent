---
name: Skill Formatos
description: Estructuras de salida obligatorias para análisis y contacto.
scope: STRUCTURAL_ONLY
version: 2.0
---

# Protocolos Estrictos

## ATENCIÓN: PROHIBIDO CITAR ESTE ARCHIVO
Este archivo es una herramienta de proceso, NO una base de conocimiento técnico. NUNCA lo cites para fundamentar análisis de habilidades (Java, Spring, React, etc.). Úsalo solo para estructurar el reporte final.

**Formato de evaluación**

A continuación se muestra el formato de evaluación de un análisis de vacantes.

## Análisis de la Vacante
🆔 ID: [analysis_id (UUID de la DB)]
📅 Fecha: [Actual]
🔗 Fuente: [URL detectada del texto | "Origen: Texto manual"]
💻 Empresa: [Nombre] | Cargo: [Nombre]
🚩 Localidad: [Localidad (Ciudad/Provincia/Dirección/Remoto/Hybrid)]
🎯 Porcentaje: [X%]

⚖️ **Comparativa Técnica:**
[Desglosa punto por punto. Por cada requerimiento de la vacante, evalúa la competencia técnica basada estrictamente en el CV del usuario]
- [Ej. "3 años de experiencia en Spring Boot"] | Análisis: [Ej. "Tu CV refleja FastAPI/Python. No hay experiencia en Spring Boot, brecha crítica en el ecosistema Java."]

💡 **Observaciones y Riesgos:**
[Análisis profundo del stack, infraestructura, metodologías y dominio de negocio solicitado. Explica la curva de aprendizaje real y justifica el impacto de las deficiencias encontradas.]

✅ Veredicto: [Apto | No apto]
🌟 TL;DR: [Resumen ejecutivo de alto nivel: máximo 3 líneas]

📝 **¿Cómo quieres continuar?**
1. [DECISIÓN] Generar borrador formal (si detectaste EMAIL) o Generar carta de presentación (si es PORTAL).
2. Generar preguntas frecuentes para entrevista técnica.
3. ¿Tienes dudas adicionales sobre este análisis? (Activa Modo Discusión).

## Borrador de Correo (Formal)
Este es el borrador del correo:

- **Para:** [Email detectado en la oferta]
- **Asunto:** [Asunto profesional y directo]
- **Cuerpo:** [Redacción basada en `skill-redaccion.md` con todos los hipervínculos Markdown intactos]
- **Firma:** [Según formato definido en `skill-contacto.md`]

Aquí tienes un link directo para abrirlo en tu gestor de correo:
[📩 Abrir borrador en tu gestor de correo](mailto:[Email]?subject=[Asunto_Encoded]&body=[Cuerpo_Encoded])

## Instrucciones para el Agente
- **Cero citas:** No incluyas marcadores de origen (ej. [cite: 1]) en el texto final.
- **Formato estricto:** Si la oferta es portal, NO generes el formato "Borrador Formal". Entrega exclusivamente la "Carta de Presentación".
- **ID:** Usar el `analysis_id` (UUID) generado al persistir el análisis en la DB.
- **Comparativa:** Cada línea debe usar el formato `- [Requisito] | Análisis: [evaluación]` con pipe literal. No repetir la palabra "Requisito:" al inicio.
