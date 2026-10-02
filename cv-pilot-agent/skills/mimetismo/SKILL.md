---
name: mimetismo
description: "Redacta correos y cartas con la voz del usuario mediante ejemplos actuales."
scope: GLOBAL
---

# Mimetismo

Usa los ejemplos del usuario para imitar su voz: vocabulario, tono, formalidad, ritmo, conectores y cierres.

## Flujo

1. Identifica la intención: correo, carta de presentación o pregunta.
2. Para una comunicación saliente: `cli.py context --job <job_hash> --mode <email|cover-letter>`.
3. Usa `examples` solo para la voz y `profile_facts` más el job para el contenido.
4. Ejecuta el comando según la intención: `email`, `cover-letter` o `question`.
5. Para flags, opciones y provisto/footer de cada comando, ejecuta `cli.py --help` o `cli.py <command> --help` (por ejemplo, `cover-letter --help` ya indica que no usa proveedor ni footer).

## Correo y carta son acciones distintas

La carta sigue la estructura de `context --mode cover-letter` (su `contract`), no la de un correo; no convierte el análisis interno de la vacante en texto visible.

| | Correo (`email`) | Carta (`cover-letter`) |
| --- | --- | --- |
| Proveedor / borrador | Gmail u Outlook; crea borrador | Ninguno; texto para copiar y pegar |
| Footer y enlaces de contacto | Sí: firma y bloque de enlaces | **No** |
| Marcado como enviada | Sí | **No** |
| Marcadores `[github]`, `[linkedin]`, `[cv]`, `[whatsapp]` | Sí | No aplican |
| Cierre | Según el contrato del correo | Con cortesía, con la voz del usuario; menciona el CV una sola vez, dentro del cuerpo |

## Ejemplos de estilo

Los ejemplos reales se cargan desde `data/correos.md` mediante `context`. No inventes ejemplos con datos de una persona concreta. Regla de calidad: conecta la experiencia del candidato con la vacante de forma narrativa y natural, nunca con tono genérico de IA (AI slop).

## Fuentes y límites

- `examples`: solo voz y estilo; `profile_facts`: únicos hechos permitidos sobre el candidato; `job` y `analysis`: contexto y necesidades del puesto.
- No inventes información ni conviertas una inferencia en un hecho.
- No leas el `perfil.json` completo si `context` ya entregó los hechos necesarios.

## Formato HTML

Partir de `assets/email-body.html` y reemplazar los párrafos. Es HTML, nunca texto plano; separar con `<p>` o `<br><br>` y no depender de `\n` (Outlook los colapsa). El CLI inyecta firma y enlaces.

- `email`: escribe HTML y usa `--dry-run` para previsualizar antes de crear un borrador.
