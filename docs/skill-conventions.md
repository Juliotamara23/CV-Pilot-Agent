# Convenciones de los `SKILL.md`

Este documento fija **la forma que siguen los contratos de skill de CV-Pilot** y registra de forma
explícita por qué **no** adoptamos la estructura de la guía LLM-first de skills del ecosistema.

No lo carga el agente en cada sesión: existe para que una persona (o un agente futuro) no lea la otra
guía, vea que nuestros skills "no cumplen" e intente arreglarlos.

## La forma del proyecto

Un `SKILL.md` de CV-Pilot es **documentación breve y operativa de cómo usar una herramienta**. El
contrato de uso real lo publica el CLI en `--help`, y el código es la fuente de verdad.

**Frontmatter**

```yaml
---
name: <slug del directorio>          # debe coincidir con el nombre de la carpeta
description: "<una línea, entre comillas>"
scope: GLOBAL | SOURCING_PHASE | DATA | STRUCTURAL_ONLY
version: "X.Y"                       # opcional
required_in_flujo: true              # opcional; lo lee el gate
---
```

**Cuerpo** — lo mínimo para decidir e invocar:

- **cuándo** usar la skill y qué la distingue de sus vecinas;
- **reglas duras** y límites (lo que el agente no puede violar);
- **orden del procedimiento** cuando importa;
- **entrypoint** exacto y sus comandos de alto nivel;
- **códigos de error** y envelope de salida;
- **Output Contract** cuando la skill produce algo que el usuario ve.

**Lo que NO va en el contrato:**

- tablas de flags, defaults, tipos y rangos — eso lo genera `--help` desde el código;
- ejemplos largos de markup, plantillas o esquemas — eso va en `assets/` del propio skill;
- historia, motivación ni explicación pedagógica.

## Desviación explícita de la guía LLM-first

La guía del ecosistema (`skill-improver` → `references/skill-style-guide.md`) exige:

| Requisito de la guía | Por qué no lo aplicamos acá |
|---|---|
| Estructura fija: Activation Contract → Hard Rules → Decision Gates → Execution Steps → Output Contract → References | Nuestros contratos usan la forma del proyecto. `AGENTS.md` **rutea sobre ella** y el gate la exige: `Check C` lee `## Flujo` y `required_in_flujo`, y `Check B` lee el registro bidireccional. Adoptarla rompería nuestro propio gate para ganar **cero** en runtime. |
| Frontmatter con `license`, `metadata.author`, `metadata.version` | Existen para acreditar skills de terceros **distribuidos** en un registry. Los nuestros son contratos internos del producto; su frontmatter es funcional (`scope`, `required_in_flujo` los consume el tooling del repo). |
| `description` con prefijo `"Trigger: ..."` | El registry del ecosistema indexa por texto de trigger. Nuestro ruteo es por paso en `AGENTS.md`, no por ese índice. |

**Sí adoptamos de la guía** los principios que aportan valor real y no chocan con lo anterior:

- **presupuesto de tokens** por contrato — impuesto por `Check F` (≤ 700);
- **prohibido duplicar el `--help`** — impuesto por `Check F` en la práctica y por `Check G` en el orquestador;
- **Output Contract** donde la skill devuelve algo visible;
- **mover a `assets/`** en vez de borrar (plantillas, esquemas, fixtures);
- **tablas de decisión** en las bifurcaciones reales, en lugar de ramas escritas en prosa;
- **sin URLs externas** como referencia primaria.

## Guardas automáticas

`cv-pilot-agent/scripts/pre_push_check.py` corre en cada push y hace cumplir lo anterior:

| Check | Qué cuida |
|---|---|
| **B** | Registro bidireccional entre `AGENTS.md` y `skills/` |
| **C** | Cobertura de `## Flujo` para los skills declarados como `required_in_flujo` |
| **F** | Presupuesto de tokens por `SKILL.md` (≤ 700), con la misma severidad sin importar el estimador |
| **G** | `AGENTS.md` no duplica: sin bloques de código ni flags de CLI salvo `--help` |

`Check F` y `Check G` fallan si su ámbito no matchea nada: un check que escanea cero archivos no está
verificando y **no puede aprobar**.

## Regla de oro

Antes de recortar o reescribir un `SKILL.md`, correr `skill-improver` en modo auditoría y leer su guía.
Ese paso se omitió una vez y costó una tanda de retrabajo: los contratos se recortaron sin confrontar el
estándar, y la desviación quedó implícita en lugar de decidida.
