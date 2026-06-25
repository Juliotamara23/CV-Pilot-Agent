"""Pydantic models mirroring the SQL schema in ``scripts/init.py``.

Field names are verbatim SQL column names (no translation) per the SDD design
refinement #4. ``Status`` is a closed ``Literal`` matching the CHECK constraint
in the jobs table.
"""

from typing import Literal, Optional

from pydantic import BaseModel

Status = Literal["new", "analyzed", "discarded", "applied", "rejected"]

VALID_STATUSES: tuple[str, ...] = ("new", "analyzed", "discarded", "applied", "rejected")


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


class Analysis(BaseModel):
    """Full analysis row, including generated id and timestamp."""

    analysis_id: str
    job_hash: str
    percentage: float
    comparativa: str
    observaciones: str
    verdict: str
    tldr: str
    created_at: Optional[str] = None