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

```
    Estimado/a Responsable de Selección,

    Le escribo para expresar mi gran interés en la posición de **Líder de Proyectos de Innovación** en **AeroTech Dynamics**, una vacante que se ajusta de manera ideal a mi trayectoria profesional en la gestión de iniciativas tecnológicas y la optimización de procesos operativos.

    A lo largo de mi carrera, he dirigido equipos multidisciplinarios en el desarrollo e implementación de soluciones digitales de alto impacto. En mi último rol, fui responsable de coordinar la transición hacia metodologías ágiles en diversos departamentos, lo que derivó en una reducción del 25% en los tiempos de entrega de proyectos y un incremento significativo en la satisfacción de los clientes clave. Mi enfoque combina la planificación estratégica, la gestión eficiente del riesgo y una comunicación clara entre los equipos técnicos y las áreas de negocio.

    Lo que más me atrae de AeroTech Dynamics es su constante apuesta por el desarrollo de tecnología sostenible y su cultura de mejora continua. Estoy convencido/a de que mi capacidad para alinear objetivos estratégicos con la ejecución táctica me permitirá aportar valor inmediato a los nuevos lanzamientos y proyectos de la compañía.

    Agradezco de antemano su tiempo y consideración al revisar mi solicitud. Quedo a su entera disposición para mantener una entrevista y conversar en detalle sobre cómo mi experiencia y habilidades pueden contribuir al crecimiento continuado de AeroTech Dynamics.

    Atentamente,

    **Candidato/a**
```

### Ejemplo negativo: IA slop

```
     La vacante pide infraestructura, redes, Microsoft 365 y proveedores. Mi perfil encaja en automatización, scripting Python/Bash, Docker, CI/CD y cloud GCP — base para infraestructura moderna. El gap es administración pura de redes (MPLS, firewalls) y Microsoft 365; mi fortaleza es backend y automatización. El salario 4.5M es atractivo. La ubicación 90% Santa Rosa de Osos implica desplazamiento semanal desde Medellín, reserva para mí.
```

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

- `cover-letter`: devuelve texto plano listo para copiar y pegar; no usa proveedor ni footer.
- `email`: escribe HTML y usa `--dry-run` para previsualizar antes de crear un borrador.
- Los marcadores `[github]`, `[linkedin]`, `[cv]` y `[whatsapp]` solo corresponden al flujo de **email**.

Ejemplo:

```html
<p>Buenos días,</p>
<p>Me postulo a la vacante y presento brevemente la experiencia relevante.</p>
<p>Quedo atento a su respuesta.</p>
```
