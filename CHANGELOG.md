# Changelog

All notable changes to CV-Pilot Agent are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.3] - 2026-07-28

### Changed
- **cv-update**: eliminada la dependencia de API key externa (`CV_PILOT_LLM_API_KEY`,
  `CV_PILOT_LLM_ENDPOINT`, `CV_PILOT_LLM_MODEL`). El CLI ahora sigue un flujo en
  dos pasos donde el script solo hace trabajo deterministico (PDF -> texto, VSI,
  JSON I/O) y el agente maneja la extraccion inteligente de campos con su propio LLM.
- **cv-update**: contrato CLI roto intencionalmente. El comando unico
  `cli.py <pdf>` se reemplaza por dos subcomandos: `extract <pdf>` y
  `apply <fields.json> [--source-pdf] [--data-dir]`.
- `_lib/llm_extract.py`: eliminada `_call_llm()` (HTTP directo con `httpx`).
  Nueva API publica: `build_extraction_prompt()`, `parse_llm_fields()`,
  `parse_llm_json()`, `parse_cv_text_with_regex()`.

### Added
- `cv-update extract`: nuevo subcomando que expone `text`, `links`, `prompt`
  y `vsi` para que el agente procese con su LLM.
- `cv-update apply --source-pdf`: flag para preservar la ruta del PDF original
  en el campo `fuente` de `perfil.json`.
- `.github/pull_request_template.md`: template de PR adaptado al stack Python
  (pytest, venv).

### Fixed
- `extract` ahora incluye `links` del PDF en su output (antes el agente no
  tenia acceso a los hipervinculos de LinkedIn/GitHub).
- `parse_llm_fields()` ahora preserva campos no canonicos (certificaciones,
  proyectos, idiomas) en lugar de descartarlos.
- `reconstructor.py`: acepta listas/objetos en `extras` (antes solo strings).
- `reconstructor.py`: maneja valores `None` en campos canonicos sin crash.

## [3.0.2] - 2026-07-23

### Fixed
- `pre_push_check.py`: offset bug in deprecation-hint detection now excludes
  only fenced code blocks (not inline backticks), so Check A no longer
  vacuously passes when all paths use markdown backtick formatting.
- `pre_push_check.py`: word-boundary `\b` regex replaces substring matching
  in Flujo coverage; a skill named `api` no longer false-matches inside
  `apify`.
- `pre_push_check.py`: `is_file()` guards and try/except with traceback
  replace raw crash on missing `AGENTS.md`.
- `pre_push_check.py`: `REQUIRED_FLUJO_SKILLS` derived from
  `required_in_flujo: true` frontmatter in `skills/*/SKILL.md` instead of
  hardcoded constant.
- `pre_push_check.py`: removed dead code (`SKIP_DIRS`, `INLINE_CODE_PATTERN`,
  `strip_code_blocks`).
- `test_cv_update.py` / `test_llm_extract.py`: replaced hardcoded Windows
  paths with repo-relative paths; tests now run on Linux/WSL.
- `docs/outlook-setup.md`: normalized voseo ("elegís" → "eliges",
  "dejalo" → "déjalo") to neutral Spanish.
- `docs/agent.md`: fixed broken links to setup guides (resolved to correct
  relative paths).

### Added
- `cv-pilot-agent/scripts/hooks/pre-push` tracked hook script with
  `python3`/`python` fallback for cross-platform support.
- `cv-pilot-agent/scripts/install-hooks.sh` idempotent installer (backs up
  existing hook, validates source exists, exits on failure).

## [3.0.1] - 2026-07-17

### Fixed
- Registered `cv-update` skill in `cv-pilot-agent/AGENTS.md` after the skill
  was created in commit 6e8f5a7 but never wired to the orchestrator's
  Flujo. Production caught the gap only when a user tried to update their
  profile and the agent reran the full onboarding flow. The Flujo now
  points to `cv-update` when the user asks to update an existing profile.

### Added
- `cv-pilot-agent/scripts/pre_push_check.py` validates three categories
  of breakage: broken path references in orchestrator markdown files,
  bidirectional registration between `AGENTS.md` and `skills/`, and
  Flujo coverage of declared skills. The script exits non-zero when any
  check fails.
- `cv-pilot-agent/scripts/hooks/pre-push` and
  `cv-pilot-agent/scripts/install-hooks.sh` — tracked hook and installer.
  Run `bash cv-pilot-agent/scripts/install-hooks.sh` once per clone to
  activate the pre-push gate.

## [3.0.0] - 2026-07-14

### Added
- Scriptification: every skill is now a CLI contract invoked by
  `cv-pilot-agent/.venv/Scripts/python.exe skills/<skill>/scripts/cli.py`.
  Token usage per skill invocation dropped from 800-1200 to 25-50.
- `cv-update` skill: rewrites `data/perfil.json` from a new CV PDF
  (snapshot semantics, no merge) for ATS fidelity.
- `_lib/` shared library: `pdf_parser`, `vsi`, Pydantic schemas,
  `llm_extract`. Replaces duplicated logic across skills.
- `AGENTS.md` v5.0: orchestrator index (84 to 58 lines). 24 redundancies
  with skills/rules removed; rule loading is now an explicit agent
  responsibility.

### Changed
- VSI (Validacion Semantica de Identidad) in `_lib/vsi.py` rejects
  non-CV documents (shopping lists, invoices, recipes) before parsing.
- Profile, preferences, and emails now use JSON + Pydantic schemas.
  Legacy markdown templates are reference only.
- Test suite grew to 251 tests (1 skipped) across
  `test/scenarios/agent-mode/`.
