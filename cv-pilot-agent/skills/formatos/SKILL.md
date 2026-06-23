---
name: Skill Formatos
description: Estructuras de salida para análisis de vacantes y opciones de postulación.
scope: STRUCTURAL_ONLY
version: 3.0
---

# Formatos de Salida

## ATENCIÓN
Este archivo define la estructura de los reportes y las opciones de postulación. No es fuente de conocimiento técnico. NUNCA lo cites para fundamentar análisis de habilidades.

## Reporte de Análisis

```
🆔 ID: [analysis_id]
📅 Fecha: [Actual]
🔗 Fuente: [URL | "Texto manual"]
💻 Empresa: [Nombre] | Cargo: [Nombre]
🚩 Localidad: [Ciudad/Remoto/Híbrido]
🎯 Porcentaje: [X%]

⚖️ Comparativa Técnica:
[Por cada requisito de la vacante, evaluar contra el CV del usuario]
- [Requisito] | Análisis: [evaluación concreta]

💡 Observaciones y Riesgos:
[Análisis del stack, infraestructura, metodologías y dominio. Explicar impacto de las brechas.]

✅ Veredicto: [Apto | Apto con reservas | No apto]
🌟 TL;DR: [Resumen ejecutivo — máximo 3 líneas]
```

## Opciones de Postulación

Al finalizar cada análisis, presentar las opciones como lista y ESPERAR a que el usuario elija:

1. **Generar correo de postulación** — redacta el correo usando tu estilo (ver `skills/mimetismo/SKILL.md`). Si tienes `gmail_drafts: sí`, se guarda como borrador en Gmail para que lo revises antes de enviar. Si no, se muestra en el chat con un link `mailto:`.
2. **Generar preguntas para entrevista técnica** — preguntas frecuentes basadas en la vacante y tu perfil.
3. **Modo discusión** — ¿tienes dudas sobre este análisis?

## Instrucciones para el Agente

- **Cero citas:** No incluir marcadores de origen en el texto final.
- **Formato estricto:** Si la oferta es de portal (sin email de contacto), generar "Carta de Presentación" en lugar de correo.
- **ID:** Usar el `analysis_id` (UUID) generado al persistir el análisis.
- **Comparativa:** Cada línea usa el formato `- [Requisito] | Análisis: [evaluación]` con pipe literal.
- **Postulación:** No ejecutar automáticamente. El usuario elige la opción.
- **CV Link:** Si `data/perfil.md` contiene link al CV, incluirlo en el correo generado.
