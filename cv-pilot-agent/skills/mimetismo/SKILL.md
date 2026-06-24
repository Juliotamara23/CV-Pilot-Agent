---
name: Skills Mimetismo Estratégico
description: Gestión de voz del usuario para cualquier comunicación saliente.
scope: GLOBAL
---

# Guía de Mimetismo Estratégico

## Objetivo
Configurar el estilo de redacción para CUALQUIER comunicación saliente (correos, respuestas a preguntas técnicas de portales, cartas de presentación). El agente debe redactar asumiendo la voz del usuario, manteniendo un tono profesional, estratégico y humilde.

## Estrategia de Contenido (Anti-Genérico)
Para que cualquier respuesta sea de alto impacto, el agente debe:
1. **Identificar el "Pain Point":** ¿Qué es lo más difícil que pide la oferta?
2. **Cruzar con Logros:** Seleccionar del CV los logros más cercanos a ese dolor.
3. **Mimetismo de Estilo:** Extraer la estructura y patrones de `data/correos.md`.
4. **Filtro de Humildad:** Usar "He implementado", "Tengo experiencia con" en lugar de "Soy un experto en".
5. **Links formateados:** Si `data/perfil.md` contiene link al CV (Drive, repositorio), LinkedIn o GitHub, incluirlos como hipervínculos HTML en el cuerpo del correo. Por ejemplo:
   `Mi <a href="https://github.com/Juliotamara23">GitHub</a>` en lugar de la URL cruda. Esto aplica tanto para correos en Gmail (--html) como en Outlook (contentType: HTML).

## Aplicación
Esta skill se aplica en cualquier comunicación saliente: correos de postulación, cartas de presentación y respuestas a cuestionarios técnicos de portales.

## Salida estructurada (cuando borradores están activados)
Tras redactar un correo, leer `data/preferencias.md`.

- Si `gmail_drafts: sí` o `outlook_drafts: sí`, emitir el correo con marcadores estructurados para que la skill correspondiente (Gmail u Outlook) pueda extraer los campos:

```
---TO: rrhh@empresa.com
---SUBJECT: Postulación: Cargo
---BODY:
Cuerpo del correo...
```

  El cuerpo continúa hasta el final del bloque del correo.

- Si el usuario indica "sin borrador" para este correo, omitir los marcadores y mostrar el correo en el chat. La preferencia global se mantiene para futuros correos.



## Scripts de Respaldo
*(Vacío — si un script generado resuelve un vacío permanente, se documenta aquí con su propósito y uso.)*
