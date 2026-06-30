"""LinkedIn adapter — wraps the ``curious_coder/linkedin-jobs-scraper`` actor.

LinkedIn's actor takes one or more *search URLs* (not raw keywords), so this
adapter builds the URL from the normalized params via LinkedIn's ``f_WT``
(workplace type) and ``f_E`` (experience level) filters. The actor requires a
minimum of 10 results per run, so :meth:`min_count` returns 10; the dispatcher
clamps the requested count and warns the user.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from .base import JobInsert, PlatformAdapter, SearchParams

ACTOR = "curious_coder/linkedin-jobs-scraper"

_WORKPLACE_TO_FWT = {"onsite": "1", "remote": "2", "hybrid": "3"}
_EXPERIENCE_TO_FE = {"entry": "2", "mid": "3", "senior": "4"}


class LinkedinAdapter(PlatformAdapter):
    def get_actor(self) -> str:
        return ACTOR

    def get_platform_name(self) -> str:
        return "apify-linkedin"

    def min_count(self) -> int:
        return 10

    def build_input(self, params: SearchParams) -> dict:
        count = max(params.count, self.min_count())
        url = self._build_search_url(params)
        return {
            "urls": [url],
            "scrapeCompany": True,
            "count": count,
            "splitByLocation": False,
        }

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

    def normalize_output(self, raw_items: list[dict]) -> list[JobInsert]:
        source = self.get_platform_name()
        jobs: list[JobInsert] = []
        for raw in raw_items:
            ext_id = raw.get("id")
            jobs.append(
                JobInsert(
                    company=self._pick(raw, "companyName", "company"),
                    position=self._pick(raw, "title"),
                    location=self._pick(raw, "location"),
                    external_id=str(ext_id) if ext_id is not None else None,
                    public_date=raw.get("postedAt"),
                    url=raw.get("link") or raw.get("url"),
                    salary=raw.get("salary") or raw.get("salaryInsights"),
                    description=raw.get("description"),
                    source=source,
                )
            )
        return jobs