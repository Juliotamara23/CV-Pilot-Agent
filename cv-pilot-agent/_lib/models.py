"""Pydantic models mirroring the SQL schema in ``scripts/init.py``.

Field names are verbatim SQL column names (no translation) per the SDD design
refinement #4. ``Status`` is a closed ``Literal`` matching the CHECK constraint
in the jobs table. ``Verdict`` is a closed ``Literal`` matching the allowed
business values for analysis verdicts.
"""

from typing import Literal, Optional

from pydantic import BaseModel

Status = Literal["new", "analyzed", "discarded", "applied", "rejected"]

VALID_STATUSES: tuple[str, ...] = ("new", "analyzed", "discarded", "applied", "rejected")

Verdict = Literal["No apto", "Apto con reservas", "Apto"]

VALID_VERDICTS: tuple[str, ...] = ("No apto", "Apto con reservas", "Apto")


def validate_status(value: str) -> str:
    """Validate that *value* is a legal job status; raise ``ValueError`` otherwise.

    Centralises the status-check so callers (db.py, query.py) do not duplicate
    the ``if value not in VALID_STATUSES`` guard.
    """
    if value not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{value}'. Must be one of: {', '.join(VALID_STATUSES)}"
        )
    return value


def validate_verdict(value: str) -> str:
    """Validate that *value* is a legal analysis verdict; raise ``ValueError`` otherwise.

    Centralises the verdict-check so callers (db.py, query.py) do not duplicate
    the ``if value not in VALID_VERDICTS`` guard.
    """
    if value not in VALID_VERDICTS:
        raise ValueError(
            f"Invalid verdict '{value}'. Must be one of: {', '.join(VALID_VERDICTS)}"
        )
    return value


class JobInsert(BaseModel):
    """Input shape for inserting a single job. Hash/computed fields excluded."""

    company: str
    position: str
    location: str
    external_id: Optional[str] = None
    public_date: Optional[str] = None
    url: Optional[str] = None
    salary: Optional[str] = None
    description: Optional[str] = None
    source: str = "manual"


class Job(BaseModel):
    """Full job row, including the primary key and persisted status."""

    job_hash: str
    company: str
    position: str
    location: str
    external_id: Optional[str] = None
    public_date: Optional[str] = None
    url: Optional[str] = None
    salary: Optional[str] = None
    description: Optional[str] = None
    status: Status = "new"
    source: str = "manual"


class AnalysisInsert(BaseModel):
    """Input shape for inserting an analysis row."""

    job_hash: str
    percentage: float
    comparativa: str
    observaciones: str
    verdict: str
    tldr: str
    contact_method: Optional[str] = None


class Analysis(BaseModel):
    """Full analysis row, including generated id and timestamp."""

    analysis_id: str
    job_hash: str
    percentage: float
    comparativa: str
    observaciones: str
    verdict: str
    tldr: str
    contact_method: Optional[str] = None
    created_at: Optional[str] = None


class UpdateFields(BaseModel):
    """Base for partial-update input models: has_fields() is derived from
    declared fields so a new field can never be forgotten."""

    def has_fields(self) -> bool:
        return any(
            getattr(self, field) is not None
            for field in type(self).model_fields
        )


class AnalysisUpdate(UpdateFields):
    """Input shape for updating an analysis row. All fields optional."""

    percentage: Optional[float] = None
    comparativa: Optional[str] = None
    observaciones: Optional[str] = None
    verdict: Optional[str] = None
    tldr: Optional[str] = None
    contact_method: Optional[str] = None


class JobUpdate(UpdateFields):
    """Input shape for updating non-identity job fields. All fields optional."""

    external_id: Optional[str] = None
    public_date: Optional[str] = None
    url: Optional[str] = None
    salary: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None