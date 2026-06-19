# CV-Pilot Web — Manual de Usuario

CV-Pilot Web es un orquestador de reclutamiento que funciona dentro de una gema de Google Gemini. Analiza vacantes contra tu CV sin necesidad de instalar nada.

---

## Instalación

1. Descarga o clona el repositorio.
2. Extrae los archivos de `cv-pilot-web/`.
3. Abre `user-identidad.md` y `ejemplo-correos.md`, y rellénalos con tus datos.
4. Crea una [Gema de Gemini](https://gemini.google.com/gems/view).
5. Sube estos archivos en la sección "Conocimiento":

```
AGENTS.md
ejemplo-correos.md
rule-integridad.md
user-identidad.md
rule-persona.md
skill-contacto.md
skill-formatos.md
skill-redaccion.md
```

6. En instrucciones, escribe: "Sigue las instrucciones descritas en AGENTS.md".

---

## Uso

1. Sube tu CV al conocimiento de la gema o adjúntalo en el chat.
2. El agente validará que sea un CV profesional (VSI).
3. Pega una oferta de trabajo en el chat.
4. El agente analiza las brechas técnicas y entrega un reporte con veredicto.

---

## Reporte

Cada análisis incluye:
- Porcentaje de compatibilidad
- Comparativa técnica
- Observaciones y riesgos
- Veredicto: Apto / Apto con reservas / No apto
- Opciones para continuar (carta de presentación, preguntas de entrevista)

---

## Ventajas de la versión Web

- **Sin instalación**: solo necesitas una cuenta de Google.
- **Uso gratuito**: Gemini permite uso sin costo con cuenta gratuita.
- **Sin límites de tokens**: ideal para análisis frecuentes.

---

*¿Dudas? Pregunta al agente dentro de la gema.*
