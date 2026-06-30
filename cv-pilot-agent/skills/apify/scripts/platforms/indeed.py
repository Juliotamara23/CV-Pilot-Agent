"""Indeed adapter — wraps the ``misceres/indeed-scraper`` actor."""

from __future__ import annotations

from .base import JobInsert, PlatformAdapter, SearchParams

ACTOR = "misceres/indeed-scraper"


class IndeedAdapter(PlatformAdapter):
    def get_actor(self) -> str:
        return ACTOR

    def get_platform_name(self) -> str:
        return "apify-indeed"

    def build_input(self, params: SearchParams) -> dict:
        return {
            "position": params.position,
            "country": params.country,
            "location": params.location,
            "maxItemsPerSearch": params.count,
            "parseCompanyDetails": True,
            "saveOnlyUniqueItems": True,
            "followApplyRedirects": False,
        }

    def normalize_output(self, raw_items: list[dict]) -> list[JobInsert]:
        source = self.get_platform_name()
        jobs: list[JobInsert] = []
        for raw in raw_items:
            ext_id = raw.get("id")
            jobs.append(
                JobInsert(
                    company=self._pick(raw, "company"),
                    position=self._pick(raw, "positionName", "position"),
                    location=self._pick(raw, "location"),
                    external_id=str(ext_id) if ext_id is not None else None,
                    public_date=raw.get("postedAt") or raw.get("postingDateParsed"),
                    url=raw.get("url"),
                    salary=raw.get("salary"),
                    description=raw.get("description"),
                    source=source,
                )
            )
        return jobs