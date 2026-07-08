---
name: Mimetismo — Generate CLI
description: CLI cli.py para correos, preguntas y cartas.
scope: GLOBAL
---

# cli.py CLI

La redacción la hace el agente; el envío, el script.

## Comandos

| Comando | ¿Crea borrador? | Notas |
|---|---|---|
| `email --job <h> --body-file <p> --to <e> [--provider gmail\|outlook] [--subject ...] [--dry-run]` | Sí | Bloquea si `contact_method=="portal"` |
| `question --job <h> --body-file <p>` | No | Error si cuerpo vacío |
| `cover-letter --job <h> --body-file <p> [--provider ...] [--to ...] [--subject ...] [--dry-run]` | Solo con provider+to | Funciona siempre |

## Contrato

1. Agente escribe HTML en `temp/cvp-{hash}-body.html` y pasa ruta con `--body-file`.
2. Script reemplaza `[github]`/`[linkedin]`/`[cv]`/`[whatsapp]` por `<a href>` desde `perfil.md`.
3. Provider auto-detectado de `preferencias.md`; `--provider` sobrescribe.
4. Si ambos providers `sí`, pasar `--provider` con la elección del usuario.
5. `cleanup.py` al final (éxito o error).
6. Output: JSON `{"ok":bool, ...}` a stdout, errores a stderr con `code`.
7. Proveedores: Gmail `gws`, Outlook `m365` (ver docs/gws-setup.md, docs/outlook-setup.md).

## Flags opcionales

### `--subject`

Línea de asunto personalizada. Si no se pasa, el script genera una por defecto según el modo:

| Modo | Asunto por defecto |
|---|---|
| `email` | `Postulación: <position> — <company>` |
| `cover-letter` | `Carta de presentación: <position> — <company>` |

Uso: pasar `--subject` cuando el usuario pide un asunto específico o cuando la empresa indica un formato particular (ej. "Asunto: Candidatura - Full Stack Developer").

```bash
# Asunto personalizado
python skills/mimetismo/scripts/cli.py email \
  --job <h> --body-file <p> --to rrhh@x.com \
  --subject "Candidatura: Senior React Developer"
```

### `--dry-run`

Previsualiza el HTML final (con links y firma) sin crear el borrador en el proveedor. No cambia el estado del job en la DB.

| Valor | Comportamiento |
|---|---|
| Sin flag (default) | Crea borrador en el proveedor y actualiza estado a `applied` |
| `--dry-run` | Retorna `{"ok": true, "dry_run": true, "html": "...", ...}` sin crear borrador |

Uso: pasar `--dry-run` cuando se quiere mostrar el email/cartas al usuario antes de enviar, o para debugging del HTML.

```bash
# Previsualizar sin crear borrador
python skills/mimetismo/scripts/cli.py email \
  --job <h> --body-file <p> --to rrhh@x.com --dry-run
```

**Envelope de salida con `--dry-run`:**
```json
{
  "ok": true,
  "mode": "email",
  "dry_run": true,
  "provider": "gmail",
  "to": "rrhh@x.com",
  "subject": "Postulación: React Developer — Acme Corp",
  "html": "<html>...</html>",
  "job_hash": "abc123"
}
```

## Formato del body file

El body file es **HTML, no plain text**. Outlook colapsa whitespace, así que `\n` no se renderiza como salto de línea — el script no convierte. Usar `<br><br>` entre párrafos (consistente con `signature_footer`):

```html
Buenos días,<br><br>Me postulo a la vacante de [Cargo] en [Empresa]. Soy Ingeniero de Sistemas con experiencia en [stack].<br><br>Adjunto mi Currículum para su revisión. Quedo atento a su respuesta.
```

Equivalente válido con `<p>` (los tests usan este patrón):

```html
<p>Buenos días,</p><p>Me postulo a la vacante...</p>
```

**NO escribir** plain text con `\n` — el draft llega a Outlook como una sola línea.
