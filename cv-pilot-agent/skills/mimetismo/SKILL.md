---
name: Mimetismo — Generate CLI
description: Documentación del CLI generate.py para correos, preguntas y cartas. Reemplaza los flujos prompt-based de mimetismo/contacto/gmail/outlook.
scope: GLOBAL
---

# Mimetismo — `generate.py` CLI

La redacción (voz del usuario) la hace el agente; el envío la hace un script determinista.

## Invocación

```bash
.venv/Scripts/python.exe skills/mimetismo/scripts/generate.py <command> [options]
```

**Convención:** venv-first (`.venv/Scripts/python.exe` en Windows, `.venv/bin/python` en Unix); fallback a `python`/`python3` si no hay `.venv/`.

## Comandos

- `email --job <hash> --body-file <path> --to <email> [--provider gmail|outlook] [--subject <text>] [--dry-run]`
  Crea un borrador en Gmail/Outlook. **Bloqueado** si `analyses.contact_method == "portal"` (error `PORTAL_POSTULATION`, usar `cover-letter`). Actualiza `jobs.status = 'applied'`.
- `question --job <hash> --body-file <path>`
  Devuelve el texto formateado para copiar/pegar en el portal. **No crea borrador.** Error `EMPTY_QUESTION` si el cuerpo está vacío.
- `cover-letter --job <hash> --body-file <path> [--provider gmail|outlook] [--to <email>] [--subject <text>] [--dry-run]`
  Funciona siempre. Con provider + `--to` crea borrador y marca `applied`. Sin provider (o sin `--to`) devuelve el texto.

## Contrato de body HTML

El agente escribe el cuerpo en `temp/cvp-{hash}-body.html` (UTF-8) y pasa la ruta con `--body-file`. El script:

1. Reemplaza marcadores `[github]`, `[linkedin]`, `[cv]`, `[whatsapp]` por `<a href>` desde `data/perfil.md`.
2. Agrega la firma (nombre + links de perfil) al final.
3. Detecta el provider desde `data/preferencias.md` (`gmail_drafts: sí` / `outlook_drafts: sí`); `--provider` sobrescribe. Tolerante a `sí`/`si`/`yes`/`true`.
4. Al final de cada ejecución (éxito o error) ejecuta `scripts/cleanup.py`.

## Output

JSON en stdout (éxito) o stderr (error) con `{"ok": true|false, ..., "code": "..."}`. Códigos: `JOB_NOT_FOUND`, `ANALYSIS_NOT_FOUND`, `PORTAL_POSTULATION`, `NO_PROVIDER`, `BODY_FILE_MISSING`, `PROVIDER_CLI_MISSING`, `DRAFT_FAILED`, `EMPTY_QUESTION`, `VALIDATION_ERROR`.

## Proveedores

- **Gmail:** `gws gmail +send --html --draft` (ver `docs/gws-setup.md`).
- **Outlook:** PowerShell heredoc + Microsoft Graph (ver `docs/outlook-setup.md`).

## Scripts de Respaldo
*(Vacío — si un script generado resuelve un vacío permanente, se documenta aquí con su propósito y uso.)*