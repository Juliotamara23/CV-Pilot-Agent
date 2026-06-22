---
name: Onboarding Conversacional
description: Flujo conversacional para recolectar, extraer, verificar y persistir el perfil del usuario en data/. Reemplaza la subida manual de archivos estaticos.
scope: GLOBAL
---

# Onboarding Conversacional

## Objetivo
Guiar al usuario, mediante una conversacion, para recolectar su CV, datos de contacto, ejemplos de correos y preferencias. El agente extrae la informacion, la verifica con el usuario y la persiste en archivos Markdown dentro de `data/`.

## Archivos de Salida
- `data/perfil.md` — CV unificado y datos de contacto (fuente unica de verdad, sin duplicacion).
- `data/correos.md` — ejemplos de correos para mimetismo de estilo.
- `data/preferencias.md` — preferencias del usuario (mimetismo, sector, tono, idioma).

Los templates de referencia estan en `skills/onboarding/templates/`.

## Preparacion del Directorio
`data/` es creado por el agente bajo demanda. No existe `.gitkeep` (esta excluido de git). Antes de escribir, crear el directorio si no existe.

## Paso 1: Deteccion de Estado

Al iniciar la sesion, verificar el contenido de `data/`:

1. **Si `data/perfil.md` existe y contiene los campos requeridos** (Identidad, Contacto, Experiencia):
   - Cargar el perfil de forma silenciosa y continuar el flujo normal.
   - No iniciar onboarding.

2. **Si `data/perfil.md` no existe o esta incompleto:**
   - Verificar si existe un estado de onboarding parcial en `data/.onboarding-state.md`.
   - Si existe estado parcial, retomar desde el ultimo paso completado (Paso 5).
   - Si no existe estado parcial, iniciar onboarding desde el Paso 2.

3. **Compatibilidad con flujo anterior:**
   - Si `data/` esta vacio pero existe `resources/identidad.md`, ofrecer al usuario migrar sus datos al nuevo flujo. No asumir la migracion automaticamente.

## Paso 2: Presentacion del Flujo

Mensaje al usuario (neutral, sin voseo, sin jerga regional):

> Antes de empezar a buscar vacantes, necesito configurar tu perfil. Voy a pedirte tu CV, tus datos de contacto, algunos ejemplos de correos que hayas escrito y tus preferencias de busqueda. Puedes pegar el texto directamente o subir un PDF. Empecemos por tu CV.

## Paso 3: Recoleccion del CV

Ofrecer dos caminos simultaneamente:

- **Camino A (texto):** El usuario pega el contenido del CV en el chat.
- **Camino B (PDF):** El usuario sube un archivo PDF. El agente ejecuta `scripts/pdf_parser.py` para extraer texto y enlaces.

### Manejo del Camino B
1. Ejecutar: `python scripts/pdf_parser.py <ruta_al_pdf>`
2. Leer la salida JSON:
   - `ok: true` → usar `text` y `links`.
   - `ok: false` → informar al usuario que no se pudo procesar el PDF y ofrecer el Camino A (pegar texto) o pegar enlaces manualmente.
3. Los enlaces extraidos (LinkedIn, GitHub, etc.) se guardan para el Paso 4.

### Validacion Semantica (VSI)
Aplicar la validacion del CV recibido:
- Detectar secciones clave (Experiencia, Skills, Educacion, Contacto).
- Si el documento no tiene estructura de CV profesional, rechazar con firmeza:
  > Este documento no parece un CV profesional valido. Por favor, comparte un CV real.
- Continuar solo con un CV valido.

## Paso 4: Extraccion de Campos

A partir del CV (texto o PDF) y de los enlaces extraidos, el agente identifica:

- Nombre completo
- Resumen profesional
- LinkedIn (de los enlaces o del texto)
- GitHub (de los enlaces o del texto)
- WhatsApp / telefono
- Correo electronico
- Experiencia (puestos, empresas, periodos, logros)
- Educacion
- Skills tecnicos

Si falta un campo esencial (LinkedIn, GitHub, telefono o correo), pedirlo explicitamente:
> Encontré tu CV, pero me falta tu [campo]. Puedes pegarlo aqui.

## Paso 5: Verificacion con el Usuario (Obligatoria)

Antes de escribir cualquier archivo, presentar un resumen de todo lo extraido y pedir confirmacion explicita. NUNCA escribir archivos sin confirmacion.

> Resumen de tu perfil:
> - Nombre: ...
> - LinkedIn: ...
> - GitHub: ...
> - Telefono: ...
> - Experiencia: ...
>
> ¿Es correcto? Responde "si" para confirmar o indica que hay que corregir.

- Si el usuario confirma → continuar al Paso 6.
- Si el usuario corrige → aplicar correcciones y volver a presentar el resumen.

## Paso 6: Recoleccion de Correos y Preferencias

Pedir ejemplos de correos y preferencias:

> Para redactar con tu estilo personal, necesito 2 o 3 ejemplos de correos que hayas enviado en postulaciones anteriores. Pegalos aqui. Si no tienes, podemos omitirlo y usare un tono profesional estandar.

> Por ultimo, tus preferencias:
> - Sector preferido (por ejemplo: Backend, IA, Fullstack)
> - Tono (formal, cercano, tecnico)
> - Idioma de postulacion (espanol, ingles)

Si el usuario omite los correos, escribir `data/correos.md` con una nota indicando que no se proporcionaron ejemplos.

## Paso 7: Backup y Escritura

Antes de sobrescribir un archivo existente en `data/`, crear un respaldo:

- Copiar `data/perfil.md` a `data/perfil.md.bak` (si existe).
- Copiar `data/correos.md` a `data/correos.md.bak` (si existe).
- Copiar `data/preferencias.md` a `data/preferencias.md.bak` (si existe).

Luego escribir los tres archivos usando los templates como estructura de referencia.

## Paso 8: Confirmacion y Limpieza

- Confirmar al usuario que el perfil esta configurado.
- Eliminar `data/.onboarding-state.md` si existe (onboarding completado).
- Continuar con el flujo normal del orquestador.

## Estado de Onboarding Parcial (Reanudacion)

Para soportar abandono y reanudacion entre sesiones, despues de cada paso completado, escribir `data/.onboarding-state.md` con:

```
ultimo_paso_completado: <numero de paso>
campos_recolectados: <lista>
```

Al retomar, leer este archivo y continuar desde el paso siguiente al ultimo completado. No volver a pedir datos ya recolectados.

## Reglas de Idioma
Todo texto dirigido al usuario debe estar en espanol neutral: sin voseo, sin jerga regional (sin "che", sin "dale" como instruccion, sin modismos locales). Mantener un tono profesional, calido y directo.

## Fallback
Si el usuario decide no completar el onboarding en este momento, registrar el estado parcial y continuar con un perfil estandar. El orquestador no debe insistir en la misma sesion.
