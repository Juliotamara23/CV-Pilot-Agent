"""Platform adapter ABC and shared params for the `search_jobs.py` dispatcher.

Each platform module (``linkedin.py``, ``indeed.py``, ``computrabajo.py``)
implements :class:`PlatformAdapter`; the dispatcher resolves the right adapter
from ``--platform`` and drives Apify through it. Adapters never touch the
network or the DB — they only translate between Apify's actor-specific
input/output shapes and the uniform :class:`JobInsert` schema.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, Optional

from pydantic import BaseModel, Field

from _lib.models import JobInsert  # re-exported for adapter modules

__all__ = ["SearchParams", "PlatformAdapter", "JobInsert"]

WorkplaceType = Literal["onsite", "remote", "hybrid"]
ExperienceLevel = Literal["entry", "mid", "senior"]


class SearchParams(BaseModel):
    """Normalized, validated parameters shared by every adapter."""

    position: str
    location: str
    country: str = "CO"
    count: int = Field(5, ge=1, le=100)
    workplace_type: Optional[WorkplaceType] = None
    experience_level: Optional[ExperienceLevel] = None


class PlatformAdapter(ABC):
    """Uniform contract every platform module must implement."""

    @abstractmethod
    def get_actor(self) -> str:
        """Return the Apify actor full name (``owner/name``)."""

    @abstractmethod
    def build_input(self, params: SearchParams) -> dict:
        """Translate search params into the actor-specific input dict."""

    @abstractmethod
    def normalize_output(self, raw_items: list[dict]) -> list[JobInsert]:
        """Map actor-specific fields onto :class:`JobInsert` rows."""

    @abstractmethod
    def get_platform_name(self) -> str:
        """Source suffix written to every JobInsert (``apify-<platform>``)."""

    # -- hooks with sane defaults ---------------------------------------- #
    def min_count(self) -> int:
        """Minimum results the actor accepts (LinkedIn clamps to 10)."""
        return 1

    # -- shared helpers -------------------------------------------------- #
    @staticmethod
    def _pick(raw: dict, *keys, default: str = "") -> str:
        """Return the first non-empty value among ``keys`` (or ``default``)."""
        for key in keys:
            value = raw.get(key)
            if value not in (None, ""):
                return str(value)
        return default