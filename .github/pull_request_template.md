## Checklist del desarrollador

Antes de marcar este PR como listo para review, confirmá cada ítem:

- [ ] Este PR cierra un issue existente: **Closes #`<issue>`**
- [ ] El código no tiene errores de sintaxis (`python -m py_compile` sobre los archivos modificados)
- [ ] Ejecuté los tests y pasan (`.venv/bin/python -m pytest test/ -v`)
- [ ] No introduje `print()` de debug ni `breakpoint()`
- [ ] No commiteé archivos `.env` (usar `.env.example` como referencia)
- [ ] Si modifiqué contratos de CLI, actualicé el `SKILL.md` correspondiente
- [ ] Hice rebase con `main` antes de abrir este PR (`git pull origin main --rebase`)

## Issue relacionado

Closes #`<issue>`

## Resumen de cambios

<!-- Describí qué hace este PR en 2-3 líneas. -->

## Cómo probar

<!-- Pasos para verificar que los cambios funcionan. -->
