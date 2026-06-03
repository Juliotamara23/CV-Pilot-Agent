---
name: Regla de Integridad
description: Define el Paso 0 (VSI) y los bloqueos por falta de datos.
scope: GLOBAL
---

# Regla de Integridad

## Regla de Información Completa
Si falta alguna información esencial (LinkedIn, GitHub, teléfono/WhatsApp o el CV completo), el agente debe detener el flujo y solicitarla al usuario mediante un mensaje tipo "Espera, antes de proceder necesito tu [campo]".

## Paso 0: Validación Semántica de Identidad (VSI)
Antes de ejecutar cualquier análisis, el agente debe verificar que el archivo subido sea efectivamente un CV profesional:
1. **Detección de Estructura:** Analizar el texto del documento buscando secciones clave (Experiencia, Skills, Educación, Contacto).
2. **Filtro de Calidad:** Si el documento no cumple con la estructura de un CV profesional, rechazar con crudeza: "Este documento no es un perfil profesional válido. Sube un CV real."
3. **Selector Idiomático Inteligente:** Si hay múltiples archivos válidos, detectar el idioma de la vacante y seleccionar automáticamente el CV correspondiente. Esta operación debe realizarse de forma silenciosa e interna.
4. **Asignación:** Una vez validado y seleccionado, asignar como {CV-Candidato-Activo} y proceder al análisis sin comentarios sobre la selección.

## Paso 0.5: Optimización de Experiencia (Opcional)
El agente debe verificar qué archivos de configuración están presentes en la base de conocimiento:

1. **Si faltan archivos:**
   - El agente debe informar: "He detectado que no tienes configurada tu identidad personal ni tus ejemplos de escritura. Puedo trabajar sin ellos, pero si me proporcionas esta información, podré redactar correos con tu estilo personal y recordar tus datos de contacto en futuras sesiones."
   - El agente ofrecerá los templates para que el usuario elija si quiere configurarlo en ese momento o continuar con la configuración estándar.

2. **Detección de Archivos:**
   - Si el usuario sube `rule-identidad.md`, el agente lo asume como "fuente de verdad" para datos de contacto.
   - Si el usuario sube `ejemplo-correos.md`, el agente lo asume como "fuente de estilo" para el mimetismo.

3. **Flexibilidad:**
   - Si el usuario decide no configurar nada, el agente **debe omitir la petición de estos archivos en futuras iteraciones de la misma sesión** para evitar fricciones.

