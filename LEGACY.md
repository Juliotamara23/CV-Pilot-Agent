# Legacy Branch Notice

Esta rama (`legacy`) preserva el estado del proyecto **antes** de la
scriptification completa y la capa de extracción con LLM.

## Por qué existe

- El `main` actual (`a68d52b` en el momento del archivado) incluye la
  v3.0.0 scriptification, la skill `cv-update`, la VSI, los schemas
  Pydantic, la extracción con LLM y el comando `formatos all`.
- Esta rama queda como referencia histórica del código previo.

## Diferencias con `main`

| Aspecto | `legacy` (esta rama) | `main` |
|---------|---------------------|--------|
| Extracción de campos del CV | Regex determinista | LLM (chat o externo) + regex fallback |
| Persistencia del perfil | `data/perfil.md` (markdown) | `data/perfil.json` (Pydantic) |
| Validación de CV | No había | VSI en `_lib/vsi.py` |
| Comando "análisis completo" | No existía | `formatos all` (P3) |
| Token usage por skill invocation | Alto (Markdown interpretado por LLM) | Bajo (CLI determinista) |
| Probabilidad de improvisación del LLM | Alta (regex rígido fallaba con CVs no estándar) | Baja (Pydantic valida, fallback explícito) |

## Estado

- **No mantener.** No se aceptan PRs contra esta rama.
- Solo se conserva para referencia histórica y comparación.
- Para trabajar, usar `main` o la rama de feature activa.
