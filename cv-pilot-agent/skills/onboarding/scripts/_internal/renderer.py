"""Template rendering for CV-Pilot onboarding.

Replaces ``{{key}}`` placeholders in template files with field values.
"""

from __future__ import annotations

import re
from pathlib import Path

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def render_template(template_path: Path, fields: dict) -> str:
    """Read template and replace each ``{{key}}`` with ``fields.get(key, '')``.

    Unknown placeholders are replaced with an empty string so the rendered file
    never leaks a literal ``{{...}}`` token.
    """
    text = template_path.read_text(encoding="utf-8")
    return _PLACEHOLDER.sub(
        lambda m: str(fields.get(m.group(1), "") or ""), text
    )


def email_block(fields: dict) -> str:
    """Render the email examples block from parsed fields."""
    examples = fields.get("email_examples")
    if isinstance(examples, list) and examples:
        blocks = []
        for idx, ex in enumerate(examples, 1):
            blocks.append(f"### Ejemplo {idx}\n{ex}")
        return "\n\n".join(blocks)
    return "_(No se proporcionaron ejemplos de correos.)_"
