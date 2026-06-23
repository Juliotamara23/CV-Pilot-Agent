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

Al finalizar cada análisis, presentar las opciones según el método de contacto detectado por `skills/contacto/SKILL.md`. NUNCA ejecutar automáticamente — el usuario elige.

### Si se detectó email de contacto

1. **Generar correo de postulación** — redacta el correo usando tu estilo (`skills/mimetismo/SKILL.md`). Si `gmail_drafts: sí`, se guarda como borrador en Gmail. Si `outlook_drafts: sí`, se guarda como borrador en Outlook (ver `docs/outlook-setup.md`). Si ambos están activos, el agente pregunta al usuario a qué proveedor guardar el correo. Si ninguno está activo, se muestra en el chat con link `mailto:`.
2. **Generar preguntas para entrevista técnica** — preguntas frecuentes basadas en la vacante y tu perfil.
3. **Modo discusión** — ¿tienes dudas sobre este análisis?

### Si NO se detectó email (`PORTAL_POSTULATION`)

1. **Generar carta de presentación** — texto para copiar y pegar en el portal de postulación, redactado con tu estilo (`skills/mimetismo/SKILL.md`).
2. **Generar preguntas para entrevista técnica** — igual que arriba.
3. **Modo discusión** — igual que arriba.

## Instrucciones para el Agente

- **Cero citas:** No incluir marcadores de origen en el texto final.
- **Email vs Portal:** La skill `contacto/SKILL.md` retorna `PORTAL_POSTULATION` cuando no hay email. Usar esto para decidir qué opciones mostrar.
- **ID:** Usar el `analysis_id` (UUID) generado al persistir el análisis.
- **Comparativa:** Cada línea usa el formato `- [Requisito] | Análisis: [evaluación]` con pipe literal.
- **CV Link:** Si `data/perfil.md` contiene link al CV, incluirlo en el correo o carta generados.
