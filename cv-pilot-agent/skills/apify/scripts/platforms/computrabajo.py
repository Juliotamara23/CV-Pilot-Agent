"""Computrabajo adapter — wraps the ``shahidirfan/computrabajo-jobs-scraper`` actor.

Computrabajo is a LATAM board with one subdomain per country. The actor takes a
single search URL shaped ``https://<sub>/trabajo-de-<keyword>-en-<location>``;
this adapter infers the subdomain from ``country``, slugifies the keyword and
location, and drops the location segment when the user asks for ``Remote``.
"""

from __future__ import annotations

from .base import JobInsert, PlatformAdapter, SearchParams

ACTOR = "shahidirfan/computrabajo-jobs-scraper"

_SUBDOMAINS = {
    "CO": "co.computrabajo.com",
    "AR": "ar.computrabajo.com",
    "MX": "mx.computrabajo.com",
    "PE": "pe.computrabajo.com",
    "CL": "cl.computrabajo.com",
}


class ComputrabajoAdapter(PlatformAdapter):
    def get_actor(self) -> str:
        return ACTOR

    def get_platform_name(self) -> str:
        return "apify-computrabajo"

    def build_input(self, params: SearchParams) -> dict:
        url = self._build_search_url(params)
        return {
            "searchUrl": url,
            "maxJobs": params.count,
            "includeFullDescription": True,
        }

    @staticmethod
    def _build_search_url(params: SearchParams) -> str:
        sub = _SUBDOMAINS.get(params.country.upper(), "co.computrabajo.com")
        keyword = ComputrabajoAdapter._slugify(params.position)
        url = f"https://{sub}/trabajo-de-{keyword}"
        if params.location.strip().lower() != "remote":
            url += f"-en-{ComputrabajoAdapter._slugify(params.location)}"
        return url

    @staticmethod
    def _slugify(text: str) -> str:
        return text.strip().lower().replace(" ", "-")

    def normalize_output(self, raw_items: list[dict]) -> list[JobInsert]:
        source = self.get_platform_name()
        jobs: list[JobInsert] = []
        for raw in raw_items:
            ext_id = raw.get("id")
            jobs.append(
                JobInsert(
                    company=self._pick(raw, "company", "companyName"),
                    position=self._pick(raw, "title", "jobTitle"),
                    location=self._pick(raw, "location"),
                    external_id=str(ext_id) if ext_id is not None else None,
                    public_date=raw.get("postedAt") or raw.get("date"),
                    url=raw.get("url") or raw.get("link"),
                    salary=raw.get("salary"),
                    description=raw.get("description"),
                    source=source,
                )
            )
        return jobs