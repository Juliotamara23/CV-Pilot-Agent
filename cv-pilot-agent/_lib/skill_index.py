"""Deterministic skill index builder.

Scans ``skills/*/SKILL.md`` frontmatter and produces a sorted, deterministic
JSON index.  Skills with missing or malformed frontmatter are excluded with a
warning to stderr; the process exits 0 as long as the skills root exists.

CLI: ``python -m _lib.skill_index list``
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SkillRecord(BaseModel):
    name: str
    description: str
    scope: str
    version: str | None = None
    triggers: list[str] = Field(default_factory=list)
    path: str
    subcommands: list[str] = Field(default_factory=list)
    required_in_flujo: bool = False
    model_config = {"frozen": True}


class SkillIndex(BaseModel):
    skills: list[SkillRecord]
    generated_at: datetime
    source_root: str = "skills"
    model_config = {"frozen": True}


_FM_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, Any] | None:
    m = _FM_RE.match(text)
    if m is None:
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def _derive_triggers(description: str) -> list[str]:
    tokens = re.split(r"[\s,;./()\-—`]+", description.lower())
    seen: set[str] = set()
    return sorted(t for t in tokens if t and len(t) > 1 and t not in seen and not seen.add(t))


def _record(fm: dict[str, Any], dir_name: str) -> SkillRecord | None:
    name, desc, scope = fm.get("name"), fm.get("description"), fm.get("scope")
    if not name or not desc or not scope:
        return None
    version = str(fm["version"]) if fm.get("version") is not None else None
    sub = fm.get("subcommands")
    if sub is None:
        subcmds: list[str] = []
    elif isinstance(sub, list):
        subcmds = [str(s) for s in sub]
    else:
        subcmds = [str(sub)]
    return SkillRecord(
        name=str(name), description=str(desc), scope=str(scope),
        version=version, triggers=_derive_triggers(str(desc)),
        path=f"skills/{dir_name}/SKILL.md", subcommands=subcmds,
        required_in_flujo=bool(fm.get("required_in_flujo", False)),
    )


def build_index(skills_root: Path | None = None) -> SkillIndex:
    root = skills_root or Path("skills")
    if not root.is_dir():
        print(f"error: skills root not found: {root}", file=sys.stderr)
        raise SystemExit(1)

    records: list[SkillRecord] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        md = d / "SKILL.md"
        if not md.is_file():
            continue
        fm = _parse_frontmatter(md.read_text(encoding="utf-8"))
        if fm is None:
            print(f"warning: skipping {md} — missing or malformed frontmatter", file=sys.stderr)
            continue
        rec = _record(fm, d.name)
        if rec is None:
            print(f"warning: skipping {md} — required fields missing", file=sys.stderr)
            continue
        records.append(rec)

    records.sort(key=lambda r: r.name)
    return SkillIndex(skills=records, generated_at=datetime.now(timezone.utc), source_root="skills")


def _to_json(index: SkillIndex) -> str:
    return json.dumps(index.model_dump(mode="json"), sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def write_index_snapshot(index: SkillIndex, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_json(index), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] != "list":
        print("usage: python -m _lib.skill_index list", file=sys.stderr)
        raise SystemExit(1)
    print(_to_json(build_index()), end="")


if __name__ == "__main__":
    main()
