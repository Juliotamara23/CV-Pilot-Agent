---
name: Mimetismo — Generate CLI
description: Contrato de redacción con la voz del usuario + CLI cli.py para correos, preguntas y cartas.
scope: GLOBAL
---

# Redacción con Mimetismo (OBLIGATORIO)

Toda comunicación saliente (email, cover-letter, question) se redacta imitando los ejemplos de correos del usuario. Los ejemplos delatan su forma de hablar (saludo, tono, estructura, cierre).

## Paso obligatorio: `cli.py mimetismo`

Ejecutar `python skills/mimetismo/scripts/cli.py mimetismo` ANTES de redactar cualquier comunicación saliente.

- **`has_examples: true`** → los `examples` recibidos SON la voz del usuario. Uso obligatorio, no opcional.
- **`has_examples: false`** → sugerir al usuario configurar sus ejemplos de correos; mientras tanto, redactar con estilo profesional estándar.

---

## Paso obligatorio: `cli.py context --job <h>`

Ejecutar `python skills/mimetismo/scripts/cli.py context --job <h>` ANTES de redactar. Es la ÚNICA fuente determinista para el borrador y separa por fuente lo que el modelo puede usar:

- **`examples`** (completos, `data/correos.md`): ÚNICA fuente de ESTILO (voz, ritmo, estructura de párrafos, conectores, cierres). No es fuente de contenido técnico.
- **`profile_facts`** (verificados de `perfil.json`, cada uno con su campo `field` que atribuye el origen): la ÚNICA fuente de afirmaciones de perfil. Solo puede afirmarse lo que esté listado.
- **`job`** + **`analysis`**: la vacante y su análisis. Los requisitos se traducen en evidencia del perfil (`profile_facts`), NUNCA se copian como párrafo-resumen genérico (ej. "La oferta encaja: buscan X").
- **`footer`**: los enlaces de contacto que la CLI añadirá en la firma. NUNCA repetirlos en el cuerpo (ni GitHub, ni LinkedIn, ni WhatsApp, ni CV, ni email, ni teléfono).

## Contrato de carta de presentación (cover-letter)

Ejecutar `python skills/mimetismo/scripts/cli.py context --job <h> --mode cover-letter` ANTES de redactar una carta de presentación. Devuelve el mismo contexto de `context --job <h>` (examples, profile_facts, certificaciones/remote_work, footer) MÁS un campo `contract` dedicado con la estructura profesional de la carta, distinta del email:

1. **Presentación** — quién eres y la vacante objetivo.
2. **Experiencia relevante** — los requisitos de la oferta traducidos en evidencia de `profile_facts`.
3. **Conexión con el rol** — cómo el perfil responde a las necesidades específicas de la vacante.
4. **Motivación** — interés genuino por la empresa y el rol.
5. **CV y cierre** — menciona el CV una vez y cierra con cortesía; el footer es del CLI.

La carta reutiliza `data/correos.md` SOLO para la voz (tono, saludo, ritmo, cierre); el contenido técnico sale de `profile_facts` y del análisis de la vacante. La carta sigue la estructura profesional del `contract` — cada sección se redacta según lo que debe contener, sin banear redacciones específicas. Se mantienen las salvaguardas de fuente: certificaciones, remote-work, años de experiencia y no-duplicación del footer.

El modelo NO debe releer `data/perfil.json`: `context` ya entrega el subconjunto verificado y atribuido por fuente. `profile_facts` excluye la expectativa salarial (privada) y los enlaces de contacto (propiedad del footer).

## Salvaguardas deterministas (afirmaciones sin soporte quedan prohibidas)

| Afirmación | Redactar SÓLO si |
| --- | --- |
| Certificaciones | El nombre exacto está en `certificaciones`. Si `certificaciones` es `[]`, no mencionar ninguna. |
| Trabajo remoto | `remote_work` es `true`. Si es `false`, no afirmar remoto. |
| Años de experiencia | Exactamente lo que declara `resumen`, sin inflar. |

## Límite: tono sí, contenido NO

`correos.md` define SOLO el tono (saludo, formalidad, estructura de párrafos, frases de cierre, firma). NUNCA es fuente de skills, experiencia ni logros: el contenido técnico SIEMPRE sale del perfil actual (`perfil.json`) y del análisis de la vacante. Los ejemplos pueden estar desactualizados.

---

## Paso obligatorio: `cli.py cv`

Ejecutar `python skills/mimetismo/scripts/cli.py cv` ANTES de redactar. Informa dónde está el CV real persistido y si existe.

- **`exists: true`** → el correo se envía con el CV adjunto (`attached: true`). Redactar "Adjunto mi Currículum" y `[cv]` se resuelve a texto plano.
- **`exists: false`** → sin adjunto; `[cv]` usa el link `cv_url` si existe. **Sugerir al usuario subir su CV real (cv-update) para que se adjunte en futuros correos.**

---

# cli.py CLI

La redacción la hace el agente; el envío, el script.

## Comandos

| Comando | ¿Crea borrador? | Notas |
| --- | --- | --- |
| `email --job <h> --body-file <p> --to <e> [--provider gmail\|outlook] [--subject ...] [--dry-run]` | Sí | Bloquea si `contact_method=="portal"` |
| `question --job <h> --body-file <p>` | No | Error si cuerpo vacío |
| `cover-letter --job <h> --body-file <p>` | No | Devuelve el artefacto copia-pega de la carta (sin footer de email ni provider) |
| `mimetismo` | No | Devuelve los ejemplos de `data/correos.md` (fuente de estilo). `has_examples: false` si no existen |
| `context --job <h> [--mode email\|cover-letter]` | No | Contexto de generación determinista y separado por fuente: `examples` (estilo), `profile_facts` (hechos verificados atribuidos), `certificaciones`/`remote_work` (salvaguardas) y `footer` (enlaces no duplicables). `--mode cover-letter` añade el `contract` con la estructura profesional de la carta de presentación |
| `cv` | No | Devuelve info del CV real persistido (exists/path/filename). `exists: true` = el correo llevará adjunto |

## Contrato

1. Agente escribe HTML en `temp/cvp-{hash}-body.html` y pasa ruta con `--body-file`.
2. Script reemplaza `[github]`/`[linkedin]`/`[cv]`/`[whatsapp]` por `<a href>` desde `perfil.json`.
3. Provider auto-detectado de `preferencias.json`; `--provider` sobrescribe.
4. Si ambos providers `sí`, pasar `--provider` con la elección del usuario.
5. `cleanup.py` al final (éxito o error).
6. Output: JSON `{"ok":bool, ...}` a stdout, errores a stderr con `code`.
7. Proveedores: Gmail `gws`, Outlook `m365` (ver docs/gws-setup.md, docs/outlook-setup.md).
8. Si `cli.py cv` reporta `exists: true`, el borrador se crea con el CV adjunto (`attached: true` en el output).

> Los pasos 3-4 y 7-8 (provider, borrador y adjunto) aplican SOLO al modo `email`. El comando `cover-letter` es una acción distinta: devuelve el artefacto copia-pega, no añade el footer de email ni invoca ningún provider.

## Flags opcionales

### `--subject`

Línea de asunto personalizada (solo para el modo `email`, que crea borrador). Si no se pasa, el script genera una por defecto:

| Modo | Asunto por defecto |
| --- | --- |
| `email` | `Postulación: <position> — <company>` |

La carta de presentación no usa `--subject`: el comando `cover-letter` devuelve un artefacto copia-pega sin crear borrador ni enviar.

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
| --- | --- |
| Sin flag (default) | Crea borrador en el proveedor y actualiza estado a `applied` |
| `--dry-run` | Retorna `{"ok": true, "dry_run": true, "html": "...", ...}` sin crear borrador |

Uso: pasar `--dry-run` cuando se quiere mostrar el email al usuario antes de enviar, o para debugging del HTML. (El `--dry-run` es del modo `email`; `cover-letter` no crea borrador).

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
