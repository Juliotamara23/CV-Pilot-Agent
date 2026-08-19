"""Tests for the CV parser in scenario06.py.

Covers both CV formats:
1. Plain header: "Backend: Python, PostgreSQL"
2. Markdown bold with dash: "- **Backend**: Python, PostgreSQL"
"""

import sys
from pathlib import Path

# Add scenario06's parent dir to path
SCENARIO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCENARIO_DIR))

from scenario06 import _parse_habilidades, load_user_data


class TestParseHabilidades:
    """Tests for _parse_habilidades function."""

    def test_plain_category_format(self):
        """Parse plain 'Category: tech1, tech2' format."""
        text = """Backend: Python (FastAPI), PostgreSQL
Frontend: React, TypeScript
DevOps & Cloud: Docker, AWS"""
        stack = _parse_habilidades(text)

        assert "backend" in stack
        assert "frontend" in stack
        assert "devops_cloud" in stack

        # Check backend entries (databases are separated into bases_de_datos)
        backend_names = [name for name, _ in stack["backend"]]
        assert "Python" in backend_names
        # PostgreSQL should be in bases_de_datos, not backend
        assert "bases_de_datos" in stack
        db_names = [name for name, _ in stack["bases_de_datos"]]
        assert "PostgreSQL" in db_names

        # Check frontend entries
        frontend_names = [name for name, _ in stack["frontend"]]
        assert "React" in frontend_names
        assert "TypeScript" in frontend_names

    def test_markdown_bold_category_format(self):
        """Parse markdown '- **Category**: tech1, tech2' format (as in Ana-CV.md)."""
        text = """- **Backend**: Python (FastAPI), PostgreSQL
- **Frontend**: React, TypeScript
- **DevOps & Cloud**: Docker, AWS"""
        stack = _parse_habilidades(text)

        assert "backend" in stack
        assert "frontend" in stack
        assert "devops_cloud" in stack

        backend_names = [name for name, _ in stack["backend"]]
        assert "Python" in backend_names
        # PostgreSQL should be in bases_de_datos
        assert "bases_de_datos" in stack
        db_names = [name for name, _ in stack["bases_de_datos"]]
        assert "PostgreSQL" in db_names

    def test_mixed_category_formats(self):
        """Parse mixed plain and markdown formats in same CV."""
        text = """Backend: Python (FastAPI), PostgreSQL
- **Frontend**: React, TypeScript
DevOps & Cloud: Docker, AWS"""
        stack = _parse_habilidades(text)

        assert "backend" in stack
        assert "frontend" in stack
        assert "devops_cloud" in stack

    def test_ia_automatizacion_category(self):
        """Parse IA & Automatización category (with special characters)."""
        text = """- **IA & Automatización**: n8n, Model Context Protocol (MCP), LLM Integration (Claude/OpenAI)
- **Backend**: Python"""
        stack = _parse_habilidades(text)

        assert "ia_automatizacion" in stack
        ia_names = [name for name, _ in stack["ia_automatizacion"]]
        assert "n8n" in ia_names
        assert "Model Context Protocol" in ia_names or "MCP" in [a for _, aliases in stack["ia_automatizacion"] for a in aliases]

    def test_parenthetical_sub_items(self):
        """Parse parenthetical sub-items like 'Python (FastAPI, Pandas)'."""
        text = """Backend: Python (FastAPI, Pandas, SQLAlchemy), PostgreSQL"""
        stack = _parse_habilidades(text)

        backend_names = [name for name, _ in stack["backend"]]
        assert "Python" in backend_names
        # PostgreSQL should be in bases_de_datos
        assert "bases_de_datos" in stack
        db_names = [name for name, _ in stack["bases_de_datos"]]
        assert "PostgreSQL" in db_names

        # Check aliases include sub-items
        python_entry = next((aliases for name, aliases in stack["backend"] if name == "Python"), None)
        assert python_entry is not None
        assert "fastapi" in python_entry
        assert "pandas" in python_entry
        assert "sqlalchemy" in python_entry

    def test_continuation_lines(self):
        """Parse category with continuation lines."""
        text = """Backend: Python (FastAPI),
    PostgreSQL, Redis
Frontend: React"""
        stack = _parse_habilidades(text)

        backend_names = [name for name, _ in stack["backend"]]
        assert "Python" in backend_names
        # PostgreSQL and Redis are databases, should be in bases_de_datos
        assert "bases_de_datos" in stack
        db_names = [name for name, _ in stack["bases_de_datos"]]
        assert "PostgreSQL" in db_names
        assert "Redis" in db_names

    def test_database_separation(self):
        """Verify databases are separated from backend into bases_de_datos."""
        text = """Backend: Python (FastAPI), PostgreSQL, MongoDB, Redis"""
        stack = _parse_habilidades(text)

        # PostgreSQL, MongoDB, Redis should be in bases_de_datos
        assert "bases_de_datos" in stack
        db_names = [name for name, _ in stack["bases_de_datos"]]
        assert "PostgreSQL" in db_names
        assert "MongoDB" in db_names
        assert "Redis" in db_names

        # Python should remain in backend
        if "backend" in stack:
            backend_names = [name for name, _ in stack["backend"]]
            assert "Python" in backend_names
            assert "PostgreSQL" not in backend_names


class TestLoadUserData:
    """Tests for load_user_data using real test/cv-test/ files."""

    def test_load_user_data_from_real_files(self):
        """load_user_data should parse real test/cv-test/ files correctly."""
        user_data = load_user_data()

        # Identity from identidad.md
        assert user_data["identity"]["name"] == "Julio Andrés Támara Hernández"
        assert "linkedin.com" in user_data["identity"]["linkedin"]
        assert "github.com" in user_data["identity"]["github"]

        # Title from Ana-CV.md
        assert user_data["identity"]["title"] == "Ingeniero de Software"

        # Stack from Ana-CV.md (markdown bold format)
        stack = user_data["stack"]
        assert "ia_automatizacion" in stack
        assert "backend" in stack
        assert "frontend" in stack
        assert "devops_cloud" in stack

        # Check specific technologies from Ana-CV.md
        all_tech_names = []
        for entries in stack.values():
            all_tech_names.extend([name for name, _ in entries])

        assert "n8n" in all_tech_names
        assert "Python" in all_tech_names
        assert "React" in all_tech_names
        assert "TypeScript" in all_tech_names
        assert "Docker" in all_tech_names

        # Aliases should be populated
        assert len(user_data["all_aliases"]) > 0

        # Primary categories should be set
        assert len(user_data["primary_categories"]) > 0

        # Total items should be non-zero
        assert user_data["total_items"] > 0

    def test_load_user_data_nonzero_tech_extraction(self):
        """Verify nonzero technology extraction from real CV."""
        user_data = load_user_data()

        # Should extract at least 10 technologies from Ana-CV.md
        assert user_data["total_items"] >= 10

        # Should have at least 4 categories
        assert len(user_data["stack"]) >= 4

        # Each category should have at least 1 technology
        for cat, entries in user_data["stack"].items():
            assert len(entries) >= 1, f"Category {cat} has no technologies"


class TestParseHabilidadesEdgeCases:
    """Edge cases for the parser."""

    def test_empty_input(self):
        """Empty input returns empty stack."""
        stack = _parse_habilidades("")
        assert stack == {}

    def test_whitespace_only(self):
        """Whitespace-only input returns empty stack."""
        stack = _parse_habilidades("   \n  \n  ")
        assert stack == {}

    def test_unknown_category_ignored(self):
        """Unknown categories are mapped to lowercase underscore key."""
        text = """Unknown Category: Python, Java"""
        stack = _parse_habilidades(text)
        # Unknown category gets normalized key
        assert "unknown_category" in stack

    def test_category_with_no_techs(self):
        """Category with no technologies is skipped."""
        text = """Backend:
Frontend: React"""
        stack = _parse_habilidades(text)
        assert "frontend" in stack
        assert "backend" not in stack or len(stack.get("backend", [])) == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
