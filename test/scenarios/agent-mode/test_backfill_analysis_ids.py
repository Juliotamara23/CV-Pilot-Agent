"""Tests for the backfill analysis ids migration (backfill NULL ids + dedupe analyses).

Reproduces the production dirty state in a throwaway DB:
  * duplicate analyses per job_hash (no UNIQUE constraint),
  * rows with ``analysis_id`` NULL (old rows predating uuid generation).
"""

import sqlite3

import pytest

from _lib import db
from _lib.models import AnalysisInsert, JobInsert


def _insert_null_id_analysis(conn, job_hash, percentage, verdict):
    """Insert an analysis row directly with a NULL analysis_id (old shape)."""
    conn.execute(
        "INSERT INTO analyses (job_hash, percentage, comparativa, observaciones, "
        "verdict, tldr) VALUES (?, ?, ?, ?, ?, ?)",
        (job_hash, str(percentage), "c", "o", verdict, "t"),
    )


class TestBackfillAnalysisIds:
    def _seed_dirty_state(self, tmp_db):
        """One job with two duplicate analyses: old NULL-id row + newer row."""
        conn = sqlite3.connect(str(tmp_db))
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        _insert_null_id_analysis(conn, h, 10.0, "No apto")  # older, NULL id
        conn.commit()
        # Newer row via the normal path (gets a uuid). Inserted after the NULL
        # one, so its rowid is greater — the rowid tiebreak must keep this one.
        newer = db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=20.0, comparativa="c", observaciones="o",
            verdict="Apto con reservas", tldr="t",
        ))
        conn.close()
        return h, newer["analysis_id"]

    def test_dry_run_reports_without_mutating(self, tmp_db):
        h, _ = self._seed_dirty_state(tmp_db)
        result = db.backfill_analysis_ids_and_dedupe(dry_run=True, db_path=str(tmp_db))
        assert result["ok"] is True
        assert result["dry_run"] is True
        assert result["backfilled"] == 1
        assert result["deduped_deleted"] == 1
        # Nothing mutated: still 2 analyses, one NULL id.
        conn = sqlite3.connect(str(tmp_db))
        n = conn.execute("SELECT COUNT(*) FROM analyses WHERE job_hash = ?", (h,)).fetchone()[0]
        nulls = conn.execute("SELECT COUNT(*) FROM analyses WHERE analysis_id IS NULL").fetchone()[0]
        conn.close()
        assert n == 2
        assert nulls == 1

    def test_real_run_backfills_and_dedupes_keeping_most_recent(self, tmp_db):
        h, _ = self._seed_dirty_state(tmp_db)
        result = db.backfill_analysis_ids_and_dedupe(dry_run=False, db_path=str(tmp_db))
        assert result["ok"] is True
        assert result["dry_run"] is False
        assert result["backfilled"] == 1
        assert result["deduped_deleted"] == 1

        # Only one analysis remains, the most recent (20% / Apto con reservas).
        got = db.get_analysis(h)["analysis"]
        assert got["percentage"] == "20.0"
        assert got["verdict"] == "Apto con reservas"
        assert got["analysis_id"] is not None

        # No NULL ids anywhere.
        conn = sqlite3.connect(str(tmp_db))
        nulls = conn.execute("SELECT COUNT(*) FROM analyses WHERE analysis_id IS NULL").fetchone()[0]
        conn.close()
        assert nulls == 0

    def test_idempotent_second_run_noop(self, tmp_db):
        h, _ = self._seed_dirty_state(tmp_db)
        db.backfill_analysis_ids_and_dedupe(dry_run=False, db_path=str(tmp_db))
        second = db.backfill_analysis_ids_and_dedupe(dry_run=False, db_path=str(tmp_db))
        assert second["backfilled"] == 0
        assert second["deduped_deleted"] == 0
        # Still exactly one analysis.
        got = db.get_analysis(h)["analysis"]
        assert got["percentage"] == "20.0"

    def test_clean_db_noop(self, tmp_db):
        h = db.insert_job(JobInsert(company="B", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=50.0, comparativa="c", observaciones="o",
            verdict="Apto", tldr="t",
        ))
        result = db.backfill_analysis_ids_and_dedupe(dry_run=False, db_path=str(tmp_db))
        assert result["backfilled"] == 0
        assert result["deduped_deleted"] == 0
        assert db.get_analysis(h)["analysis"]["verdict"] == "Apto"

    def test_migration_keeps_most_recent_when_verdict_worsens(self, tmp_db):
        """The keep-most-recent rule holds even when the new verdict is worse."""
        conn = sqlite3.connect(str(tmp_db))
        h = db.insert_job(JobInsert(company="C", position="P", location="L"))["hash"]
        _insert_null_id_analysis(conn, h, 80.0, "Apto con reservas")  # older
        conn.commit()
        db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=30.0, comparativa="c", observaciones="o",
            verdict="No apto", tldr="t",
        ))
        conn.close()
        db.backfill_analysis_ids_and_dedupe(dry_run=False, db_path=str(tmp_db))
        got = db.get_analysis(h)["analysis"]
        assert got["verdict"] == "No apto"  # the re-evaluation wins
