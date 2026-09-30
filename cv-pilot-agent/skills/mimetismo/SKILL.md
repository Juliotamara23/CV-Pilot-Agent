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

La carta sigue la estructura que entrega `context --mode cover-letter` en su `contract`, no la de un correo, y no debe transformar el análisis interno de la vacante en texto visible.

### Contrato de entrega de la carta

La carta se entrega SOLO para copiar y pegar. NO lleva:

- footer de correo ni inyección de firma automática;
- bloque final de enlaces de contacto (GitHub, LinkedIn, WhatsApp, correo, teléfono);
- proveedor (gmail/outlook) ni creación de borrador;
- marcado de la postulación como enviada.

Esos comportamientos pertenecen exclusivamente al flujo `email`. La carta cierra con cortesía usando la voz del usuario; si menciona el CV, lo hace una sola vez, dentro del cuerpo.

## Ejemplos de estilo

Los ejemplos reales se cargan desde `data/correos.md` mediante `context`. No inventes ejemplos con datos de una persona concreta. Regla de calidad: conecta la experiencia del candidato con la vacante de forma narrativa y natural, nunca con tono genérico de IA (AI slop).

## Fuentes y límites

- `examples`: solo voz y estilo; `profile_facts`: únicos hechos permitidos sobre el candidato; `job` y `analysis`: contexto y necesidades del puesto.
- No inventes información ni conviertas una inferencia en un hecho.
- No leas el `perfil.json` completo si `context` ya entregó los hechos necesarios.

## Formato HTML

El body file debe ser HTML, no texto plano. Usa `<p>` o `<br><br>` entre párrafos; no dependas de saltos de línea `\n`, porque Outlook puede colapsarlos.

- `cover-letter`: devuelve texto plano listo para copiar y pegar; no usa proveedor ni footer.
- `email`: escribe HTML y usa `--dry-run` para previsualizar antes de crear un borrador.
- Los marcadores `[github]`, `[linkedin]`, `[cv]` y `[whatsapp]` solo corresponden al flujo de **email**.
