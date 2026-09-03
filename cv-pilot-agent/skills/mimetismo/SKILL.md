---
name: Mimetismo — Generate CLI
description: Redacta correos y cartas con la voz del usuario mediante ejemplos actuales.
scope: GLOBAL
---

# Mimetismo

Usa los ejemplos del usuario para imitar su voz: vocabulario, tono, formalidad, ritmo, conectores y cierres. Los ejemplos son fuente de estilo, nunca de experiencia, habilidades o logros.

## Flujo

1. Identifica la intención: correo, carta de presentación o pregunta.
2. Para una comunicación saliente, ejecuta:

   ```bash
   python skills/mimetismo/scripts/cli.py context --job <job_hash> --mode <email|cover-letter>
   ```

3. Usa `examples` solo para la voz y `profile_facts` más el job para el contenido.
4. Ejecuta la acción correspondiente:
   - `email` crea un borrador y puede usar proveedor/footer.
   - `cover-letter` devuelve una carta para copiar y pegar; no usa proveedor ni footer.
   - `question` devuelve una respuesta para un portal.
5. Si necesitas conocer opciones o comandos adicionales, ejecuta:

   ```bash
   python skills/mimetismo/scripts/cli.py --help
   python skills/mimetismo/scripts/cli.py <command> --help
   ```

## Correo y carta son acciones distintas

### Correo

Breve y orientado a iniciar contacto. Puede incluir asunto, destinatario, CV y footer cuando el proveedor esté configurado.

### Carta de presentación

Es un documento independiente para copiar y pegar. Usa la voz de los ejemplos de correo, pero desarrolla una estructura propia:

1. presentación;
2. experiencia relevante;
3. relación natural con el puesto;
4. motivación;
5. currículum y cierre.

No conviertas la carta en un correo ni conviertas el análisis interno de la vacante en texto visible.

## Ejemplos de estilo

Los ejemplos reales se cargan desde `data/correos.md` mediante `context`. No inventes ejemplos con nombres, empresas, teléfonos, URLs, tecnologías o experiencias de una persona concreta dentro de esta skill.

### Ejemplo positivo: relación natural con el puesto

> Mi experiencia incluye el desarrollo de APIs y la automatización de procesos, por lo que me interesa aportar estas capacidades en los proyectos del equipo.

### Ejemplo negativo: análisis visible de matching

> La vacante pide A, B y C. Mi perfil encaja en X e Y. El gap está en Z.

El segundo ejemplo expone el razonamiento interno del agente. Debe transformarse en una explicación natural, manteniendo la voz observada en los ejemplos del usuario.

## Fuentes y límites

- `examples`: solo voz y estilo.
- `profile_facts`: únicos hechos permitidos sobre el candidato.
- `job` y `analysis`: contexto y necesidades del puesto.
- No inventes información ni conviertas una inferencia en un hecho.
- No leas el `perfil.json` completo si `context` ya entregó los hechos necesarios.
- No repitas contactos o footer en una carta.

## Comandos principales

| Comando | Uso |
| --- | --- |
| `context --job <hash> --mode <email\|cover-letter>` | Entrega ejemplos, hechos y contexto de redacción. |
| `email --job <hash> --body-file <path> --to <email>` | Crea un borrador de correo con el proveedor configurado. |
| `cover-letter --job <hash> --body-file <path>` | Devuelve la carta para copiar y pegar, sin footer ni proveedor. |
| `question --job <hash> --body-file <path>` | Devuelve una respuesta para un portal. |
| `mimetismo` | Devuelve los ejemplos de estilo actuales. |
| `cv` | Informa si existe un CV persistido. |

Usa `--help` para descubrir flags, proveedores y comandos no enumerados aquí.

## Formato HTML

El body file debe ser HTML, no texto plano. Usa `<p>` o `<br><br>` entre párrafos; no dependas de saltos de línea `\n`, porque Outlook puede colapsarlos.

- `email`: escribe HTML y usa `--dry-run` para previsualizar antes de crear un borrador.
- `cover-letter`: devuelve HTML o texto listo para copiar y pegar; no usa proveedor ni footer.
- Los marcadores `[github]`, `[linkedin]`, `[cv]` y `[whatsapp]` solo corresponden al flujo de correo.

Ejemplo:

```html
<p>Buenos días,</p>
<p>Me postulo a la vacante y presento brevemente la experiencia relevante.</p>
<p>Quedo atento a su respuesta.</p>
```
