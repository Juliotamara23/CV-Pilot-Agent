---
name: Regla de Integridad
description: Validación de datos al iniciar sesión. Detecta perfil ausente o incompleto y deriva al flujo de onboarding conversacional.
scope: GLOBAL
---

# Regla de Integridad

## Inicio de Sesión: Verificación de Perfil
Al iniciar cualquier sesión, el agente debe verificar el estado de `data/` antes de ejecutar cualquier análisis:

1. **Verificar `data/perfil.md`:**
   - Existe y contiene los campos requeridos (Identidad, Contacto, Experiencia) → cargar el perfil de forma silenciosa y continuar el flujo normal.
   - No existe o está incompleto → iniciar el flujo de onboarding (`skills/onboarding/SKILL.md`).

2. **Flujo de onboarding:**
   - Seguir los pasos definidos en `skills/onboarding/SKILL.md`.
   - El onboarding recolecta CV, datos de contacto, ejemplos de correos y preferencias, verifica con el usuario y persiste en `data/`.
   - No reanudar el flujo normal hasta que el perfil esté completo o el usuario decida omitirlo explícitamente.

3. **Compatibilidad con flujo anterior:**
   - Si `data/` está vacío pero existe `resources/identidad.md`, ofrecer migrar los datos al nuevo flujo. No asumir la migración automáticamente.

## Regla de Información Completa
Si falta alguna información esencial (LinkedIn, GitHub, teléfono/WhatsApp o el CV completo), el agente debe detener el flujo y solicitarla al usuario mediante un mensaje del tipo:

> Antes de proceder necesito tu [campo]. Puedes pegarlo aquí o subirlo como PDF.

## Validación Semántica de Identidad (VSI)
Una vez que el agente dispone de un CV (texto o extraído de PDF), debe verificar que sea efectivamente un CV profesional:

1. **Detección de Estructura:** Analizar el texto buscando secciones clave (Experiencia, Skills, Educación, Contacto).
2. **Filtro de Calidad:** Si el documento no cumple con la estructura de un CV profesional, rechazar con firmeza:

   > Este documento no es un perfil profesional válido. Comparte un CV real.

3. **Selector Idiomático Inteligente:** Si hay múltiples CVs válidos, detectar el idioma de la vacante y seleccionar automáticamente el CV correspondiente. Operación silenciosa e interna.
4. **Asignación:** Una vez validado y seleccionado, asignar como CV activo y proceder al análisis sin comentarios sobre la selección.

## Regla de Silencio Operativo
- NUNCA menciones nombres de archivos de configuración en tus respuestas al usuario.
- NUNCA reportes pasos operativos internos.
- Debes operar de forma silenciosa e interna para todas las tareas de validación, selección de idioma y detección de método de postulación. El usuario solo debe ver el resultado final, no el proceso.

## Integridad de Output
- **Cero citas:** No incluir marcadores de origen ni referencias internas en el texto final que ve el usuario. El output debe ser limpio y autocontenido.
