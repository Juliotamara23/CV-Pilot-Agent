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

    # -- error filtering ------------------------------------------------- #
    def filter_errors(self, raw_items: list[dict]) -> tuple[list[dict], list[dict]]:
        """Split raw items into (valid, errors) by detecting Indeed-style error items.

        Indeed actor pushes {"error": "FOUND_NO_RESULTS", "errorDescription": "..."}
        when a search yields nothing. Other actors don't emit this today, but
        we filter at the base class so any future actor is safe.

        An item is classified as an error item when it has an "error" field AND
        lacks the critical job fields (id/title/companyName/company/positionName).
        This protects against future jobs that might have an "error" field for
        unrelated reasons.
        """
        valid: list[dict] = []
        errors: list[dict] = []
        for item in raw_items:
            if not isinstance(item, dict):
                # Malformed: not an error item per se, but not a job either.
                # Defer to the adapter's normalize_output to decide.
                valid.append(item)
                continue
            if (
                "error" in item
                and "id" not in item
                and "title" not in item
                and "companyName" not in item
                and "company" not in item
                and "positionName" not in item
            ):
                errors.append(item)
            else:
                valid.append(item)
        return valid, errors

    # -- safe normalization ---------------------------------------------- #
    def normalize_output_safe(
        self, raw_items: list[dict]
    ) -> tuple[list[JobInsert], list[dict]]:
        """Wrap ``normalize_output`` with per-item error isolation.

        Returns ``(jobs, failures)`` where *failures* contains a dict per item
        that failed Pydantic validation::

            {"id": <str>, "platform": <str>, "raw_preview": <str>, "error": <str>}

        This is an adapter-level wrapper — individual adapters keep their
        simple ``normalize_output(list) -> list`` contract unchanged.  The
        safe variant is used by the CLI so one bad item never kills the batch.
        """
        platform = self.get_platform_name()
        jobs: list[JobInsert] = []
        failures: list[dict] = []
        for idx, item in enumerate(raw_items):
            try:
                # Delegate to the adapter's concrete normalize_output for a
                # single item.  We call the existing method which returns
                # list[JobInsert]; we take element 0 since we pass one item.
                batch = self.normalize_output([item])
                if batch:
                    jobs.append(batch[0])
                else:
                    # Adapter silently dropped the item — treat as failure.
                    item_id = item.get("id", f"no_id_{idx}") if isinstance(item, dict) else f"no_id_{idx}"
                    failures.append({
                        "id": str(item_id),
                        "platform": platform,
                        "raw_preview": str(item)[:200],
                        "error": "Adapter returned empty list for this item",
                    })
            except Exception as exc:
                item_id = item.get("id", f"no_id_{idx}") if isinstance(item, dict) else f"no_id_{idx}"
                failures.append({
                    "id": str(item_id),
                    "platform": platform,
                    "raw_preview": str(item)[:200],
                    "error": str(exc),
                })
        return jobs, failures

    # -- shared helpers -------------------------------------------------- #
    @staticmethod
    def _pick(raw: dict, *keys, default: str = "") -> str:
        """Return the first non-empty value among ``keys`` (or ``default``)."""
        for key in keys:
            value = raw.get(key)
            if value not in (None, ""):
                return str(value)
        return default