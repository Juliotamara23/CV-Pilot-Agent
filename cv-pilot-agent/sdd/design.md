# Design: database-scriptification

## Technical Approach
Replace the 181-line Markdown database skill with a Typer-based Python CLI encapsulating the SQL contract. The agent invokes `query.py` via subprocess and reads JSON from stdout, eliminating ad-hoc SQL and centralizing normalization, hashing, and dedup in `_lib/`. Output matches `pdf_parser.py`: JSON stdout, errors stderr, `{"ok": bool, ...}` envelope.

## Architecture Decisions

| Decision | Choice |
|---|---|
| CLI | Typer with sub-apps (`job`, `analysis`, `status`) |
| Validation | Pydantic v2 + `Literal[...]` for status |
| Dedup | Refresh on **strictly newer** `public_date`; absent hash -> insert; else -> no-op |
| Delete | `--dry-run` flag controls count vs mutate; function always returns count |
| `analysis insert` | Single tx: INSERT row + UPDATE `jobs.status='analyzed'` |
| Naming | SQL column names verbatim: `percentage`, `verdict`, `comparativa`, `observaciones`, `tldr`, `public_date` |
| Connection | `row_factory=Row`, `journal_mode=WAL`, `foreign_keys=ON` (all PRAGMA, idempotent per connect) |
| Path | `Path(__file__).resolve().parent.parent / "db" / "cv-pilot.db"` from `_lib/db.py` — mirrors `scripts/init.py:5` |
| Normalization | `company.strip().title()`, `position.strip()`, `location.strip()`; normalized forms feed hash, originals stored |

## Data Flow

`AGENTS.md paso 3/4/4a-4d` -> `subprocess.run([python, query.py, ...])` -> Typer -> Pydantic -> `_lib/db.py` -> `sqlite3` (WAL, FK=ON, Row) -> `db/cv-pilot.db`. Output: `json.dumps(..., ensure_ascii=False)` to stdout; errors to stderr with `{"ok":false,"code":...}`.

## File Changes

| File | Action |
|---|---|
| `cv-pilot-agent/_lib/{__init__.py, db.py, models.py, errors.py}` | Create (db ~140, models ~60, errors ~30 lines) |
| `cv-pilot-agent/skills/database/scripts/{__init__.py, query.py}` | Create (query ~220, 3 sub-apps, 8 cmds) |
| `cv-pilot-agent/skills/database/SKILL.md` | Modify: 181 -> ~30 lines, CLI only, no SQL |
| `cv-pilot-agent/AGENTS.md` | Modify: pasos 3, 4, 4a-4d SQL -> script; drop SQLite CLI block |
| `cv-pilot-agent/requirements.txt` | Add `typer>=0.12`, `pydantic>=2.6` |

## Interfaces / Contracts

**`_lib/db.py`** (user-requested names verbatim; all return `dict`):

- `get_connection() -> sqlite3.Connection`
- `compute_hash(company, position, location) -> str` — SHA256 of normalized concat with `"|"` delimiter
- `insert_job(job) -> {ok, hash, is_new, is_duplicate, refreshed}`
- `insert_jobs_batch(jobs) -> {ok, inserted, refreshed, duplicates, results}`
- `list_jobs(status, limit) -> {ok, count, jobs: [...]}`
- `get_job(job_hash) -> {ok, job: {...}}` — raises `JobNotFoundError` on miss
- `delete_jobs(status, dry_run) -> {ok, deleted, dry_run}`
- `insert_analysis(analysis) -> {ok, analysis_id}` — auto UPDATE `status='analyzed'`
- `get_analysis(job_hash) -> {ok, analysis: {...}}`
- `update_status(job_hash, status) -> {ok, old_status, new_status}`

**`_lib/models.py`** (SQL column names verbatim per refinement #4):

`Status = Literal["new","analyzed","discarded","applied","rejected"]`. `JobInsert`: req `company/position/location`; opt `external_id, public_date, url, salary, description, source="manual"`. `Job` adds `job_hash, status="new"`. `AnalysisInsert`: req `job_hash, percentage: float, comparativa, observaciones, verdict, tldr`. `Analysis` adds `analysis_id, created_at`.

**`_lib/errors.py`**: `CV_PilotError` base -> `DatabaseError`, `JobNotFoundError`, `DuplicateJobError`, `ValidationError`.

**`query.py` subcommands**:

| App.Cmd | Required flags |
|---|---|
| `job.insert` | `--company --position --location` + opt metadata + `--source` |
| `job.insert-batch` | `--file PATH` (JSON array) |
| `job.list` | `[--status] [--limit 10]` |
| `job.get` | `--hash` |
| `job.delete` | `--status [--dry-run]` |
| `analysis.insert` | `--job-hash --percentage --comparativa --observaciones --verdict --tldr` |
| `analysis.get` | `--job-hash` |
| `status.set` | `--hash --status` |

**Error envelope** (stderr, exit 1): `{"ok": false, "error": "...", "code": "JOB_NOT_FOUND|DUPLICATE_JOB|VALIDATION_ERROR|DATABASE_ERROR"}`. Single Typer callback maps `_lib/errors.py` exceptions to codes.

**Batch dedup contract** (inside `insert_job`, per refinement #3):
1. `hash = compute_hash(...)`; `SELECT public_date FROM jobs WHERE job_hash = ?`.
2. Absent -> INSERT, `is_new=true`.
3. Present AND `incoming.public_date > stored` (lex ISO-8601) -> `DELETE FROM analyses WHERE job_hash=?`, `UPDATE jobs SET status='new', public_date=?, url=?, salary=?, description=? WHERE job_hash=?`, `refreshed=true`.
4. Else -> `is_duplicate=true`, no mutation.

## Testing Strategy

| Layer | What | How |
|---|---|---|
| Unit (`db.py`) | hash deterministic; insert_job new/refresh/duplicate | `pytest` + `tmp_path` DB; seed row, call with newer/older/same/missing date |
| Unit (`models.py`) | invalid Status rejected; missing required fields | pydantic assertions |
| CLI | JSON shape; exit 0/1; stderr envelope | `subprocess.run`; assert stdout keys + stderr JSON on bad input |
| Smoke | init -> insert -> list -> analysis insert -> get | one-shot e2e against `tmp_path` DB |

## Migration / Rollout

**Phase 1 — Additive:** ship `_lib/`, `query.py`, new `SKILL.md` (~30 lines). Keep old `SKILL.md` as `SKILL.md.bak` for one commit. Smoke every subcommand from REPL.

**Phase 2 — AGENTS.md:** edit pasos 3, 4, 4a-4d to invoke `query.py` instead of generating SQL. Remove the SQLite CLI install block (script uses stdlib). Run a full sourcing flow end-to-end.

**Phase 3 — Cleanup:** delete `SKILL.md.bak`, bump `AGENTS.md` 4.0 -> 4.1.

**Rollback:** `git restore skills/database/SKILL.md AGENTS.md requirements.txt; rm -rf _lib skills/database/scripts`.

## Open Questions

- [ ] `init.py` defines `analyses.job_hash` FK without `ON DELETE CASCADE`. `delete_jobs --status X` would fail on FK violation. **Recommend:** `delete_jobs` runs `DELETE FROM analyses WHERE job_hash IN (SELECT job_hash FROM jobs WHERE status=?)` first, then `DELETE FROM jobs WHERE status=?`, both in one tx. Keeps `init.py` untouched (out of scope per `rules/code_guard.md`).
- [ ] Hash delimiter `"|"` could be `"\x00"`. Cosmetic — defer.
