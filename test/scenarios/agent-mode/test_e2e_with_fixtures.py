"""Integration test: Full agent-mode flow with DB seeded from Apify fixtures.

This test proves:
1. Nonzero technology extraction from real CV (Ana-CV.md)
2. Meaningful nonzero match/verdict path when seeded fixture job has overlapping technologies
3. All DB writes under tmp_path via CV_PILOT_DB
"""

import sys
from pathlib import Path

import pytest

# Add scenario06 to path
SCENARIO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCENARIO_DIR))

from scenario06 import load_user_data, analyze_vacancy
from test_apify_seed_db import seed_db_from_fixtures, get_pending_jobs, insert_analysis


class TestFullFlowWithSeededFixtures:
    """Test the complete sourcing → mapping → persistence → analysis → verdict flow."""

    def test_linkedin_fixture_yields_nonzero_matches(self, tmp_path):
        """LinkedIn fixture jobs should have overlapping tech with user CV."""
        # Arrange: seed temp DB with LinkedIn fixture
        db_path = tmp_path / "test.db"
        inserted = seed_db_from_fixtures(db_path, "linkedin", count=5)

        assert len(inserted) > 0, "Should have inserted jobs from fixture"

        # Load user data (from test/cv-test/ - fake/test data only)
        user_data = load_user_data()

        # Verify nonzero technology extraction from CV
        assert user_data["total_items"] >= 10, "Should extract >=10 technologies from CV"
        assert len(user_data["stack"]) >= 4, "Should have >=4 categories"

        # Act: analyze each pending job
        pending = get_pending_jobs(db_path)
        assert len(pending) == len(inserted)

        results = []
        for job in pending:
            analysis = analyze_vacancy(job["description"], job["position"], user_data)
            analysis_id = insert_analysis(
                db_path,
                job["job_hash"],
                analysis["percentage"],
                analysis["comparativa"],
                analysis["observaciones"],
                analysis["verdict"],
                analysis["tldr"],
            )
            results.append({
                "job": job,
                "analysis": analysis,
                "analysis_id": analysis_id,
            })

        # Assert: at least one job should have nonzero matches
        nonzero_matches = [r for r in results if r["analysis"]["percentage"] != "0%"]
        assert len(nonzero_matches) > 0, (
            f"Expected at least one job with nonzero match. "
            f"Results: {[(r['job']['position'], r['analysis']['percentage']) for r in results]}"
        )

        # Assert: at least one job should have a meaningful verdict (not just "No apto" from 0%)
        meaningful_verdicts = [r for r in results if r["analysis"]["verdict"] in ("Apto", "Apto con reservas")]
        assert len(meaningful_verdicts) > 0, (
            f"Expected at least one Apto/Apto con reservas verdict. "
            f"Got: {[(r['job']['position'], r['analysis']['verdict'], r['analysis']['percentage']) for r in results]}"
        )

        # Assert: matched technologies should be from user's actual stack
        for r in nonzero_matches:
            matched = r["analysis"]["matched"]
            assert len(matched) > 0, "Should have matched technologies"
            # Verify matched techs are from user's stack
            all_user_techs = set()
            for entries in user_data["stack"].values():
                all_user_techs.update(name for name, _ in entries)
            for tech in matched:
                assert tech in all_user_techs, f"Matched tech '{tech}' not in user stack"

    def test_computrabajo_fixture_yields_matches(self, tmp_path):
        """Computrabajo fixture jobs should have overlapping tech with user CV."""
        db_path = tmp_path / "test.db"
        inserted = seed_db_from_fixtures(db_path, "computrabajo", count=5)

        assert len(inserted) > 0

        user_data = load_user_data()
        pending = get_pending_jobs(db_path)

        results = []
        for job in pending:
            analysis = analyze_vacancy(job["description"], job["position"], user_data)
            insert_analysis(
                db_path,
                job["job_hash"],
                analysis["percentage"],
                analysis["comparativa"],
                analysis["observaciones"],
                analysis["verdict"],
                analysis["tldr"],
            )
            results.append((job["position"], analysis["percentage"], analysis["verdict"], analysis["matched"]))

        # At least one match expected (Computrabajo fixture mentions React, TypeScript, Next.js)
        nonzero = [r for r in results if r[1] != "0%"]
        assert len(nonzero) > 0, f"No nonzero matches: {results}"

    def test_multi_platform_seeding(self, tmp_path):
        """Seeding from multiple platforms should work and produce varied matches."""
        db_path = tmp_path / "test.db"
        from test_apify_seed_db import seed_db_from_all_fixtures

        results = seed_db_from_all_fixtures(db_path, count_per_platform=3)

        total_inserted = sum(len(jobs) for jobs in results.values())
        assert total_inserted > 0

        user_data = load_user_data()
        pending = get_pending_jobs(db_path)
        assert len(pending) == total_inserted

        # Analyze all
        verdicts = []
        for job in pending:
            analysis = analyze_vacancy(job["description"], job["position"], user_data)
            insert_analysis(db_path, job["job_hash"], analysis["percentage"],
                          analysis["comparativa"], analysis["observaciones"],
                          analysis["verdict"], analysis["tldr"])
            verdicts.append((job["source"], analysis["verdict"], analysis["percentage"]))

        # Should have at least some Apto or Apto con reservas
        apto = [v for v in verdicts if v[1] in ("Apto", "Apto con reservas")]
        assert len(apto) > 0, f"No Apto verdicts: {verdicts}"

    def test_cv_parser_handles_ana_cv_markdown_format(self):
        """Verify the parser correctly handles Ana-CV.md's markdown bold format."""
        user_data = load_user_data()

        # Ana-CV.md uses "- **Category**:" format
        # Should extract all 4 categories with technologies
        stack = user_data["stack"]
        assert "ia_automatizacion" in stack
        assert "backend" in stack
        assert "frontend" in stack
        assert "devops_cloud" in stack

        # Check specific technologies from Ana-CV.md (top-level + aliases)
        all_techs = []
        for entries in stack.values():
            all_techs.extend([name for name, _ in entries])

        # Also check aliases for sub-items like FastAPI (under Python)
        all_aliases = [alias for alias, _ in user_data["all_aliases"]]

        # Key technologies that should be extracted (top-level or as aliases)
        expected_techs = ["n8n", "Python", "React", "TypeScript", "Docker", "Next.js", "Tailwind CSS"]
        for tech in expected_techs:
            assert tech in all_techs, f"Missing expected top-level tech: {tech}"

        # FastAPI is a sub-item of Python, should be in aliases
        assert "fastapi" in all_aliases, "FastAPI should be extracted as alias of Python"

        # Total items should be substantial (nonzero extraction)
        assert user_data["total_items"] >= 15


class TestScenario06And08WithFixtures:
    """Test that scenario06 and scenario08 can use the seeded DB approach."""

    def test_scenario06_load_user_data_works_with_fake_cv(self):
        """scenario06.load_user_data should work with test/cv-test/ (fake data)."""
        # This is already tested above but let's be explicit
        user_data = load_user_data()

        assert user_data["identity"]["name"] == "Julio Andrés Támara Hernández"
        assert user_data["identity"]["title"] == "Ingeniero de Software"
        assert user_data["total_items"] > 0

    def test_scenario08_imports_load_user_data(self):
        """scenario08 should import load_user_data from scenario06."""
        import scenario08
        # scenario08 imports: from scenario06 import load_user_data, analyze_vacancy
        assert hasattr(scenario08, 'load_user_data')
        assert hasattr(scenario08, 'analyze_vacancy')

        # Verify they work
        user_data = scenario08.load_user_data()
        assert user_data["total_items"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])