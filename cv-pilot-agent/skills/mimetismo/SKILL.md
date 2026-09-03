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

### Contrato de entrega de la carta

La carta se entrega SOLO para copiar y pegar. NO lleva:

- footer de correo ni inyección de firma automática;
- bloque final de enlaces de contacto (GitHub, LinkedIn, WhatsApp, correo, teléfono);
- proveedor (gmail/outlook) ni creación de borrador;
- marcado de la postulación como enviada.

Esos comportamientos pertenecen exclusivamente al flujo `email`. La carta cierra con cortesía usando la voz del usuario; si menciona el CV, lo hace una sola vez, dentro del cuerpo, sin bloques de contacto al final.

## Ejemplos de estilo

Los ejemplos reales se cargan desde `data/correos.md` mediante `context`. No inventes ejemplos con nombres, empresas, teléfonos, URLs, tecnologías o experiencias de una persona concreta dentro de esta skill. Los ejemplos genéricos de abajo ilustran el estilo deseado; no son reglas de frases prohibidas: la voz del usuario manda y cada carta se redacta según la estructura del `contract`.

### Ejemplo positivo: conexión narrativa natural

> En mi último rol me tocó un proceso manual que consumía horas cada semana. Lo descompuse, encontré los pasos que se podían automatizar y, con el equipo, lo dejamos funcionando solo; el tiempo de entrega bajó a menos de la mitad. Cuando leí que este puesto busca a alguien que simplifique flujos complejos, pensé que es justo el tipo de problema que ya sé resolver.

Por qué funciona: cuenta qué hizo (historia), qué aprendió (resultado) y por qué conecta con el puesto (relación explicada). La experiencia se muestra con una explicación natural, no se enumera contra la oferta.

### Ejemplo negativo: análisis de matching visible

> Revisé la vacante y vi que pide A, B y C. Mi perfil cumple A, tengo algo de B y me falta C, pero estoy dispuesto a aprenderlo. Mi porcentaje de ajuste con el puesto es alto y pueden verificarlo en mi CV.

Por qué no funciona: expone el razonamiento interno del agente (requisitos → encaje → gap → porcentaje). El lector ve una plantilla de análisis, no a una persona explicando por qué su experiencia sirve.

### Ejemplo negativo: recitado de requisitos

> La vacante busca experiencia en A y B, trabajo en equipo y proactividad. Yo tengo experiencia en A y B, soy proactivo y me gusta trabajar en equipo. Cumplo con lo que piden y quedo atento.

Por qué no funciona: devuelve cada requisito tal cual viene de la oferta, sin mostrar cómo se usó. Parafrasear la vacante no es conectar: cada requisito debe traducirse en evidencia concreta del perfil (`profile_facts`).

Transforma ambos patrones negativos en una explicación natural, manteniendo la voz observada en los ejemplos del usuario (sus conectores, formalidad y forma de cerrar).

## Fuentes y límites

- `examples`: solo voz y estilo.
- `profile_facts`: únicos hechos permitidos sobre el candidato.
- `job` y `analysis`: contexto y necesidades del puesto.
- No inventes información ni conviertas una inferencia en un hecho.
- No leas el `perfil.json` completo si `context` ya entregó los hechos necesarios.
- La carta no añade footer, firma ni bloque de contactos: esos elementos son exclusivos del flujo `email`.

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
