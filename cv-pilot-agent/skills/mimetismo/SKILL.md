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
| `email --job <h> --body-file <p> --to <e> [--provider gmail\|outlook] [--dry-run]` | Sí | Bloquea si `contact_method=="portal"` |
| `question --job <h> --body-file <p>` | No | Error si cuerpo vacío |
| `cover-letter --job <h> --body-file <p> [--provider ...] [--to ...] [--dry-run]` | Solo con provider+to | Funciona siempre |

## Contrato

1. Agente escribe HTML en `temp/cvp-{hash}-body.html` y pasa ruta con `--body-file`.
2. Script reemplaza `[github]`/`[linkedin]`/`[cv]`/`[whatsapp]` por `<a href>` desde `perfil.md`.
3. Provider auto-detectado de `preferencias.md`; `--provider` sobrescribe.
4. Si ambos providers `sí`, pasar `--provider` con la elección del usuario.
5. `cleanup.py` al final (éxito o error).
6. Output: JSON `{"ok":bool, ...}` a stdout, errores a stderr con `code`.
7. Proveedores: Gmail `gws`, Outlook `m365` (ver docs/gws-setup.md, docs/outlook-setup.md).

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
