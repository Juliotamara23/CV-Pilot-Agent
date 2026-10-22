"""LinkedIn adapter.

The default actor is ``curious_coder/linkedin-jobs-scraper``. It takes search
URLs, so this adapter builds the URL from workplace and experience filters.
That actor asks for at least 10 rows, and :meth:`min_count` returns 10 unless
the optional actor is selected.

Set ``CVPILOT_LINKEDIN_JOBS_ACTOR`` to ``johnvc/linkedin-jobs-api`` to send
``keyword``, ``location``, and ``maxJobs`` instead. That path does not apply
the 10-row floor.
https://apify.com/johnvc/linkedin-jobs-api
https://alphaosint.com/
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote_plus

from .base import JobInsert, PlatformAdapter, SearchParams

ACTOR = "curious_coder/linkedin-jobs-scraper"
OPTIONAL_LINKEDIN_JOBS_ACTOR = "johnvc/linkedin-jobs-api"
LINKEDIN_JOBS_ACTOR_ENV = "CVPILOT_LINKEDIN_JOBS_ACTOR"
_OPTIONAL_IDS = {
    OPTIONAL_LINKEDIN_JOBS_ACTOR,
    "johnvc~linkedin-jobs-api",
}

_WORKPLACE_TO_FWT = {"onsite": "1", "remote": "2", "hybrid": "3"}
_EXPERIENCE_TO_FE = {"entry": "2", "mid": "3", "senior": "4"}


def _optional_linkedin_jobs() -> bool:
    return os.environ.get(LINKEDIN_JOBS_ACTOR_ENV, "").strip() in _OPTIONAL_IDS


class LinkedinAdapter(PlatformAdapter):
    def get_actor(self) -> str:
        if _optional_linkedin_jobs():
            return OPTIONAL_LINKEDIN_JOBS_ACTOR
        return ACTOR

    def get_platform_name(self) -> str:
        return "apify-linkedin"

    def min_count(self) -> int:
        if _optional_linkedin_jobs():
            return 1
        return 10

    def build_input(self, params: SearchParams) -> dict:
        if _optional_linkedin_jobs():
            return self._optional_input(params)
        count = max(params.count, self.min_count())
        url = self._build_search_url(params)
        return {
            "urls": [url],
            "scrapeCompany": True,
            "count": count,
            "splitByLocation": False,
        }

    @staticmethod
    def _optional_input(params: SearchParams) -> dict:
        body: dict = {
            "keyword": params.position,
            "location": params.location,
            "maxJobs": params.count,
        }
        if params.workplace_type == "remote":
            body["remote"] = True
        elif params.workplace_type is not None:
            # Onsite and hybrid stay searchable. Remote-only would drop them.
            body["remote"] = False
        # Only "entry" is one of this actor's experience values.
        if params.experience_level == "entry":
            body["experienceLevel"] = "entry"
        return body

    @staticmethod
    def _build_search_url(params: SearchParams) -> str:
        parts = [
            "https://www.linkedin.com/jobs/search/?",
            f"keywords={quote_plus(params.position)}",
            f"&location={quote_plus(params.location)}",
        ]
        if params.workplace_type:
            parts.append(f"&f_WT={_WORKPLACE_TO_FWT[params.workplace_type]}")
        if params.experience_level:
            parts.append(f"&f_E={_EXPERIENCE_TO_FE[params.experience_level]}")
        return "".join(parts)

    @staticmethod
    def _format_salary(salary) -> Optional[str]:
        """Normalize the ``salary`` field from the LinkedIn actor.

        Real-world output (captured 2026-07-07) returns ``salary`` as a
        string. The public docs at the time showed ``salaryInfo`` as a list
        (``[min, max]``) but the live actor does NOT emit that field — the
        docs were stale. We therefore default to ``salary`` and only fall
        back to ``salaryInfo`` if the actor ever changes shape again.
        Lists are joined with ``", "``; scalars are coerced to ``str``;
        ``None``/empty returns ``None``.
        """
        if salary is None or salary == "":
            # Try the documented (but currently absent) list variant.
            return None
        if isinstance(salary, list):
            parts = [str(s).strip() for s in salary if s]
            return ", ".join(parts) if parts else None
        return str(salary)

    def _salary_text(self, raw: dict) -> Optional[str]:
        text = self._format_salary(raw.get("salary"))
        if text:
            return text
        low = raw.get("salaryMin")
        high = raw.get("salaryMax")
        if low is None and high is None:
            return None
        parts = [str(low)] if low is not None else []
        if high is not None:
            parts.append(str(high))
        text = "-".join(parts)
        currency = raw.get("salaryCurrency")
        if isinstance(currency, str) and currency.strip():
            text = f"{text} {currency.strip()}"
        return text

    def normalize_output(self, raw_items: list[dict]) -> list[JobInsert]:
        source = self.get_platform_name()
        jobs: list[JobInsert] = []
        for raw in raw_items:
            if raw.get("result_type") not in (None, "job"):
                continue
            ext_id = raw.get("id")
            if ext_id is None:
                ext_id = raw.get("jobId")
            jobs.append(
                JobInsert(
                    company=self._pick(raw, "companyName", "company"),
                    position=self._pick(raw, "title"),
                    location=self._pick(raw, "location"),
                    external_id=str(ext_id) if ext_id is not None else None,
                    public_date=raw.get("postedAt") or raw.get("postedDate"),
                    url=raw.get("link") or raw.get("url") or raw.get("jobUrl"),
                    salary=self._salary_text(raw),
                    description=(raw.get("descriptionText")
                                 or raw.get("descriptionHtml")
                                 or raw.get("description")
                                 or raw.get("summary")),
                    source=source,
                )
            )
        return jobs


from .registry import register as _register_adapter

_register_adapter("linkedin", LinkedinAdapter)