---
name: Gmail Draft
description: Guarda correos generados por mimetismo como borradores en Gmail usando el CLI gws. Gated por preferencia gmail_drafts.
scope: GLOBAL
---

# Gmail Draft — Borradores de Postulación

## Objetivo
Guardar correos de postulación generados por mimetismo como borradores en Gmail, para que el usuario los revise antes de enviarlos. Actúa como envoltorio del CLI `gws` (ver `gws-shared/SKILL.md` y `gws-send/SKILL.md`).

## Prerrequisitos
- Preferencia `gmail_drafts: sí` en `data/preferencias.md`.
- El binario `gws` instalado y autenticado (ver `gws-shared/SKILL.md`).

## Flujo de Ejecución

### 1. Verificar preferencia
Leer `data/preferencias.md` y localizar el campo `gmail_drafts`.

- `gmail_drafts: sí` → continuar.
- `gmail_drafts: no` → no hacer nada. El correo queda en el chat.
- Campo ausente → preguntar al usuario:
  > ¿Guardar como borrador en Gmail? (sí/no)
  Persistir la respuesta en `data/preferencias.md`. Solo continuar si responde "sí".

Si el usuario dice "sin borrador" para un correo puntual, omitir el borrador solo para ese correo. La preferencia global se mantiene.

### 2. Detectar `gws`
Ejecutar:
```bash
gws --version
```

- Éxito → continuar al paso 3.
- Fallo (comando no encontrado) → informar al usuario:
  > No encuentro el comando `gws`. Para guardar borradores en Gmail necesitas instalar gws (ver https://github.com/googleworkspace/cli). Mientras tanto, dejo el correo aquí para que lo envíes manualmente.
  Mostrar el correo en el chat y detener el flujo.

### 3. Extraer campos del correo
El correo generado por mimetismo incluye marcadores estructurados:

```
---TO: rrhh@empresa.com
---SUBJECT: Postulación: Cargo
---BODY:
Cuerpo del correo...
```

Extraer los tres campos (To, Subject, Body) a partir de los marcadores de prefijo `---TO:`, `---SUBJECT:`, `---BODY:`. El cuerpo continúa hasta el final del bloque del correo.

- Si falta uno o más campos → pedir al usuario el dato faltante. No continuar hasta tener los tres campos.

### 4. Confirmar con el usuario (OBLIGATORIO)
Mostrar una vista previa:

> Vista previa del borrador:
> - Para: <to>
> - Asunto: <subject>
> - Cuerpo:
> <cuerpo>
>
> ¿Confirmas? (sí/no)

Solo ejecutar `gws` si el usuario responde "sí". Ante cualquier otra respuesta, conservar el correo en el chat y no ejecutar la escritura.

### 5. Crear el borrador
Ejecutar:
```bash
gws gmail +send --to "<to>" --subject "<subject>" --body "<body>" --draft
```

Esta es una operación de **escritura** (ver `gws-shared/SKILL.md` — Security Rules), confirmada en el paso 4.

### 6. Manejo de errores

| Error | Detección | Respuesta |
|-------|-----------|-----------|
| `gws` no autenticado | `gws` retorna error de auth | Informar al usuario: "Tu sesión de gws no está autenticada. Ejecuta `gws auth login` e inténtalo de nuevo." Conservar el correo en el chat. |
| Error de la API de Gmail | `gws` retorna error HTTP de la API | Reportar el error al usuario. Conservar el correo en el chat. |
| Campos faltantes | Marcadores incompletos | Pedir al usuario el dato faltante antes de proseguir. |

En todos los casos de fallo, el correo se conserva en el chat como fallback.

## Reglas de Idioma
Todo texto dirigido al usuario debe estar en español neutral: sin voseo, sin jerga regional. Tono profesional, cálido y directo.

## Ver también
- `gws-shared/SKILL.md` — Auth, flags globales, reglas de seguridad.
- `gws-send/SKILL.md` — Comando `gmail +send` (flags completos).