---
name: Onboarding Conversacional
description: Flujo conversacional para recolectar, extraer, verificar y persistir el perfil del usuario en data/. Reemplaza la subida manual de archivos estáticos.
scope: GLOBAL
---

# Onboarding Conversacional

## Objetivo
Guiar al usuario, mediante una conversación, para recolectar su CV, datos de contacto, ejemplos de correos y preferencias. El agente extrae la información, la verifica con el usuario y la persiste en archivos Markdown dentro de `data/`.

## Archivos de Salida
- `data/perfil.md` — CV unificado y datos de contacto (fuente única de verdad, sin duplicación).
- `data/correos.md` — ejemplos de correos para mimetismo de estilo.
- `data/preferencias.md` — preferencias del usuario (mimetismo, sector, tono, idioma).

Los templates de referencia están en `skills/onboarding/templates/`.

## Preparación del Directorio
`data/` es creado por el agente bajo demanda. No existe `.gitkeep` (está excluido de git). Antes de escribir, crear el directorio si no existe.

## Paso 1: Detección de Estado

Al iniciar la sesión, verificar el contenido de `data/`:

1. **Si `data/perfil.md` existe y contiene los campos requeridos** (Identidad, Contacto, Experiencia):
   - Cargar el perfil de forma silenciosa y continuar el flujo normal.
   - No iniciar onboarding.

2. **Si `data/perfil.md` no existe o está incompleto:**
   - Verificar si existe un estado de onboarding parcial en `data/.onboarding-state.md`.
   - Si existe estado parcial, retomar desde el último paso completado (Paso 5).
   - Si no existe estado parcial, iniciar onboarding desde el Paso 2.

3. **Compatibilidad con flujo anterior:**
   - Si `data/` está vacío pero existe `resources/identidad.md`, ofrecer al usuario migrar sus datos al nuevo flujo. No asumir la migración automáticamente.

## Paso 2: Presentación del Flujo

Mensaje al usuario (neutral, sin voseo, sin jerga regional):

> Antes de empezar a buscar vacantes, necesito configurar tu perfil. Voy a pedirte tu CV, tus datos de contacto, algunos ejemplos de correos que hayas escrito y tus preferencias de búsqueda. Puedes pegar el texto directamente o subir un PDF. Empecemos por tu CV.

## Paso 3: Recolección del CV

Ofrecer dos caminos simultáneamente:

- **Camino A (texto):** El usuario pega el contenido del CV en el chat.
- **Camino B (PDF):** El usuario sube un archivo PDF. El agente ejecuta `scripts/pdf_parser.py` para extraer texto y enlaces.

### Manejo del Camino B
1. Ejecutar: `python scripts/pdf_parser.py <ruta_al_pdf>`
2. Leer la salida JSON:
   - `ok: true` → usar `text` y `links`.
   - `ok: false` → informar al usuario que no se pudo procesar el PDF y ofrecer el Camino A (pegar texto) o pegar enlaces manualmente.
3. Los enlaces extraídos (LinkedIn, GitHub, etc.) se guardan para el Paso 4.

### Validación Semántica (VSI)
Aplicar la validación del CV recibido:
- Detectar secciones clave (Experiencia, Skills, Educación, Contacto).
- Si el documento no tiene estructura de CV profesional, rechazar con firmeza:
  > Este documento no parece un CV profesional válido. Por favor, comparte un CV real.
- Continuar solo con un CV válido.

## Paso 4: Extracción de Campos

A partir del CV (texto o PDF) y de los enlaces extraídos, el agente identifica:

- Nombre completo
- Resumen profesional
- LinkedIn (de los enlaces o del texto)
- GitHub (de los enlaces o del texto)
- WhatsApp / teléfono
- Correo electrónico
- Experiencia (puestos, empresas, periodos, logros)
- Educación
- Skills técnicos

Si falta un campo esencial (LinkedIn, GitHub, teléfono o correo), pedirlo explícitamente:
> Encontré tu CV, pero me falta tu [campo]. Puedes pegarlo aquí.

## Paso 5: Verificación con el Usuario (Obligatoria)

Antes de escribir cualquier archivo, presentar un resumen de todo lo extraído y pedir confirmación explícita. NUNCA escribir archivos sin confirmación.

> Resumen de tu perfil:
> - Nombre: ...
> - LinkedIn: ...
> - GitHub: ...
> - Teléfono: ...
> - Experiencia: ...
>
> ¿Es correcto? Responde "sí" para confirmar o indica qué hay que corregir.

- Si el usuario confirma → continuar al Paso 6.
- Si el usuario corrige → aplicar correcciones y volver a presentar el resumen.

## Paso 6: Recolección de Correos y Preferencias

Pedir ejemplos de correos y preferencias:

> Para redactar con tu estilo personal, necesito 2 o 3 ejemplos de correos que hayas enviado en postulaciones anteriores. Pégalos aquí. Si no tienes, podemos omitirlo y usaré un tono profesional estándar.

> Por último, tus preferencias:
> - Sector preferido (por ejemplo: Backend, IA, Fullstack)
> - Tono (formal, cercano, técnico)
> - Idioma de postulación (español, inglés)

Si el usuario omite los correos, escribir `data/correos.md` con una nota indicando que no se proporcionaron ejemplos.

## Paso 7: Backup y Escritura

Antes de sobrescribir un archivo existente en `data/`, crear un respaldo:

- Copiar `data/perfil.md` a `data/perfil.md.bak` (si existe).
- Copiar `data/correos.md` a `data/correos.md.bak` (si existe).
- Copiar `data/preferencias.md` a `data/preferencias.md.bak` (si existe).

Luego escribir los tres archivos usando los templates como estructura de referencia.

## Paso 8: Confirmación y Limpieza

- Confirmar al usuario que el perfil está configurado.
- Eliminar `data/.onboarding-state.md` si existe (onboarding completado).
- Continuar con el flujo normal del orquestador.

## Estado de Onboarding Parcial (Reanudación)

Para soportar abandono y reanudación entre sesiones, después de cada paso completado, escribir `data/.onboarding-state.md` con:

```
ultimo_paso_completado: <número de paso>
campos_recolectados: <lista>
```

Al retomar, leer este archivo y continuar desde el paso siguiente al último completado. No volver a pedir datos ya recolectados.

## Reglas de Idioma
Todo texto dirigido al usuario debe estar en español neutral: sin voseo, sin jerga regional. Mantener un tono profesional, cálido y directo.

## Fallback
Si el usuario decide no completar el onboarding en este momento, registrar el estado parcial y continuar con un perfil estándar. El orquestador no debe insistir en la misma sesión.
