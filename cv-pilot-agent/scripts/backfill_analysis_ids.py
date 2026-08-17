"""Migration script: backfill NULL analysis ids and dedupe duplicate analyses.

Run from the repo root with the project venv::

    cv-pilot-agent/.venv/bin/python cv-pilot-agent/scripts/backfill_analysis_ids.py --dry-run
    cv-pilot-agent/.venv/bin/python cv-pilot-agent/scripts/backfill_analysis_ids.py

Steps (in one transaction, idempotent):
  1. Backfill ``analysis_id`` NULL rows with a fresh uuid4.
  2. Dedupe ``analyses`` keeping ONLY the most recent row per ``job_hash``
     (the row ``analysis get`` returns today).

The real logic lives in ``_lib/db.py::backfill_analysis_ids_and_dedupe`` so
tests can call it directly; this script is a thin CLI wrapper. Always inspect
``--dry-run`` output before running the real migration, and keep a backup of
the DB first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make cv-pilot-agent/ importable.
_AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_AGENT_ROOT))

from _lib import db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill NULL analysis ids and dedupe duplicate analyses."
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Override the database path (default: production cv-pilot.db).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without mutating anything.",
    )
    args = parser.parse_args()

    result = db.backfill_analysis_ids_and_dedupe(dry_run=args.dry_run, db_path=args.db)
    print(
        f"{'DRY-RUN ' if args.dry_run else ''}backfilled: {result['backfilled']}, "
        f"deduped_deleted: {result['deduped_deleted']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
