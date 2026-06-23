---
name: Outlook Draft
description: Guarda correos generados por mimetismo como borradores en Outlook usando el CLI m365 (CLI for Microsoft 365). Gated por preferencia outlook_drafts.
scope: GLOBAL
---

# Outlook Draft — Borradores de Postulación

## Objetivo
Guardar correos de postulación generados por mimetismo como borradores en Outlook, para que el usuario los revise antes de enviarlos. Actúa como envoltorio del CLI `m365` (CLI for Microsoft 365), que invoca Microsoft Graph para crear el borrador.

## Prerrequisitos
- Preferencia `outlook_drafts: sí` en `data/preferencias.md`.
- El binario `m365` instalado y autenticado (ver `docs/outlook-setup.md`).

## Flujo de Ejecución

### 1. Verificar preferencia
Leer `data/preferencias.md` y localizar el campo `outlook_drafts`.

- `outlook_drafts: sí` → continuar.
- `outlook_drafts: no` → no hacer nada. El correo queda en el chat.
- Campo ausente → preguntar al usuario:
  > ¿Guardar como borrador en Outlook? (sí/no)
  Persistir la respuesta en `data/preferencias.md`. Solo continuar si responde "sí".

Si el usuario dice "sin borrador" para un correo puntual, omitir el borrador solo para ese correo. La preferencia global se mantiene.

### 2. Detectar `m365`
Ejecutar:
```bash
m365 --version
```

- Éxito → continuar al paso 3.
- Fallo (comando no encontrado) → informar al usuario:
  > No encuentro el comando `m365`. Para guardar borradores en Outlook necesitas instalar y configurar CLI for Microsoft 365. Consulta la guía en `docs/outlook-setup.md` para el paso a paso. Mientras tanto, dejo el correo aquí para que lo envíes manualmente.
  Mostrar el correo en el chat y detener el flujo.

Verificar también la autenticación:
```bash
m365 status
```

- Si indica sesión activa → continuar al paso 3.
- Si indica que no hay sesión → informar al usuario:
  > Tu sesión de `m365` no está autenticada. Ejecuta `m365 login` (flujo device code) e inténtalo de nuevo. Mientras tanto, dejo el correo aquí para que lo envíes manualmente.
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

Solo ejecutar `m365` si el usuario responde "sí". Ante cualquier otra respuesta, conservar el correo en el chat y no ejecutar la escritura.

### 5. Crear el borrador
A través de Microsoft Graph. Un mensaje creado sin enviar queda automáticamente como borrador en la carpeta Borradores.

**Paso 5.1 — Obtener token de acceso:**
```powershell
$token = m365 util accesstoken get --resource "https://graph.microsoft.com" --output text
```

**Paso 5.2 — Construir el JSON del cuerpo:**
Escribir el JSON en un archivo temporal con codificación UTF-8. Esto evita problemas de escape con caracteres especiales y garantiza que tildes y eñes se conserven intactas. El JSON debe seguir esta estructura:

```json
{
  "subject": "<asunto>",
  "body": { "contentType": "Text", "content": "<cuerpo>" },
  "toRecipients": [{ "emailAddress": { "address": "<destinatario>" } }]
}
```

Guardarlo usando `Out-File` con `-Encoding utf8` o `Set-Content` con `-Encoding UTF8`:
```powershell
$bodyJson = @{
  subject = "<asunto>"
  body = @{ contentType = "Text"; content = "<cuerpo>" }
  toRecipients = @(@{ emailAddress = @{ address = "<destinatario>" } })
} | ConvertTo-Json -Depth 3
$bodyJson | Out-File -FilePath "$env:TEMP\cvpilot_outlook.json" -Encoding utf8
```

**Paso 5.3 — Crear el borrador vía Graph API:**

*PowerShell (Windows):*
```powershell
$bodyJson = Get-Content -Path "$env:TEMP\cvpilot_outlook.json" -Raw -Encoding UTF8
Invoke-RestMethod -Uri "https://graph.microsoft.com/v1.0/me/messages" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Headers @{Authorization = "Bearer $token"} `
  -Body $bodyJson
```

*Bash (Linux/Mac):*
```bash
token=$(m365 util accesstoken get --resource "https://graph.microsoft.com" --output text)
curl -X POST "https://graph.microsoft.com/v1.0/me/messages" \
  -H "Authorization: Bearer $token" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d @/tmp/cvpilot_outlook.json
```

**Nota:** `m365 request --method post --body` no se usa porque la CLI no auto-detecta el content-type para POST con body. Este enfoque con token + HTTP directo es la alternativa soportada.

### 6. Manejo de errores

| Error | Detección | Respuesta |
|-------|-----------|-----------|
| `m365` no autenticado | `m365 status` indica sin sesión | Informar al usuario: "Tu sesión de `m365` no está autenticada. Ejecuta `m365 login` e inténtalo de nuevo." Conservar el correo en el chat. |
| `m365` no instalado | `m365 --version` falla | Informar: "No encuentro `m365`. Consulta `docs/outlook-setup.md` para instalarlo." Conservar el correo en el chat. |
| Error de la API de Graph | `m365 request` retorna respuesta no 2xx | Reportar el error al usuario. Conservar el correo en el chat con un link `mailto:` como fallback. |
| Campos faltantes | Marcadores incompletos | Pedir al usuario el dato faltante antes de proseguir. |

En todos los casos de fallo, el correo se conserva en el chat como fallback, con un link `mailto:` cuando aplique.

## Ambos proveedores activos
Si `gmail_drafts: sí` Y `outlook_drafts: sí`, el agente pregunta al usuario antes de invocar cualquier skill:
> Tienes Gmail y Outlook activados como proveedores de borradores. ¿A cuál quieres que guarde este correo? (gmail/outlook)

Tras la elección, invocar la skill correspondiente. Si el usuario pide ambos, ejecutar las dos skills con confirmaciones independientes.

## Reglas de Idioma
Todo texto dirigido al usuario debe estar en español neutral: sin voseo, sin jerga regional. Tono profesional, cálido y directo.

## Ver también
- `docs/outlook-setup.md` — Instalación y configuración de `m365`.
- `skills/gmail/SKILL.md` — Skill equivalente para borradores en Gmail.