---
name: Regla de Integridad
description: Validacion de datos al iniciar sesion. Detecta perfil ausente o incompleto y deriva al flujo de onboarding conversacional.
scope: GLOBAL
---

# Regla de Integridad

## Inicio de Sesion: Verificacion de Perfil
Al iniciar cualquier sesion, el agente debe verificar el estado de `data/` antes de ejecutar cualquier analisis:

1. **Verificar `data/perfil.md`:**
   - Existe y contiene los campos requeridos (Identidad, Contacto, Experiencia) → cargar el perfil de forma silenciosa y continuar el flujo normal.
   - No existe o esta incompleto → iniciar el flujo de onboarding (`skills/onboarding/SKILL.md`).

2. **Flujo de onboarding:**
   - Seguir los pasos definidos en `skills/onboarding/SKILL.md`.
   - El onboarding recolecta CV, datos de contacto, ejemplos de correos y preferencias, verifica con el usuario y persiste en `data/`.
   - No reanudar el flujo normal hasta que el perfil este completo o el usuario decida omitirlo explicitamente.

3. **Compatibilidad con flujo anterior:**
   - Si `data/` esta vacio pero existe `resources/identidad.md`, ofrecer migrar los datos al nuevo flujo. No asumir la migracion automaticamente.

## Regla de Informacion Completa
Si falta alguna informacion esencial (LinkedIn, GitHub, telefono/WhatsApp o el CV completo), el agente debe detener el flujo y solicitarla al usuario mediante un mensaje del tipo:

> Antes de proceder necesito tu [campo]. Puedes pegarlo aqui o subirlo como PDF.

## Validacion Semantica de Identidad (VSI)
Una vez que el agente dispone de un CV (texto o extraido de PDF), debe verificar que sea efectivamente un CV profesional:

1. **Deteccion de Estructura:** Analizar el texto buscando secciones clave (Experiencia, Skills, Educacion, Contacto).
2. **Filtro de Calidad:** Si el documento no cumple con la estructura de un CV profesional, rechazar con firmeza:

   > Este documento no es un perfil profesional valido. Comparte un CV real.

3. **Selector Idiomatico Inteligente:** Si hay multiples CVs validos, detectar el idioma de la vacante y seleccionar automaticamente el CV correspondiente. Operacion silenciosa e interna.
4. **Asignacion:** Una vez validado y seleccionado, asignar como CV activo y proceder al analisis sin comentarios sobre la seleccion.

## Regla de Silencio Operativo
- NUNCA menciones nombres de archivos de configuracion en tus respuestas al usuario.
- NUNCA reportes pasos operativos internos.
- Debes operar de forma silenciosa e interna para todas las tareas de validacion, seleccion de idioma y deteccion de metodo de postulacion. El usuario solo debe ver el resultado final, no el proceso.
