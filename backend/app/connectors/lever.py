from typing import Optional

import httpx

from .base import BaseConnector, NormalizedJob


class LeverConnector(BaseConnector):
    """
    No API key required. credentials = {"site_names": "netflix,mistral"}
    (comma-separated Lever site names / company handles to track.)
    """
    source_name = "lever"

    async def search(self, keywords: str, location: Optional[str], remote_only: bool, max_results: int) -> list[NormalizedJob]:
        sites = [s.strip() for s in self.credentials.get("site_names", "").split(",") if s.strip()]
        if not sites:
            return []

        jobs: list[NormalizedJob] = []
        kw = keywords.lower()
        loc = (location or "").lower()

        async with httpx.AsyncClient(timeout=20) as client:
            for site in sites:
                if len(jobs) >= max_results:
                    break
                url = f"https://api.lever.co/v0/postings/{site}?mode=json"
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPError:
                    continue

                for item in data:
                    title = item.get("text", "")
                    categories = item.get("categories", {}) or {}
                    job_location = categories.get("location", "")
                    is_remote = "remote" in (job_location or "").lower() or categories.get("commitment", "").lower() == "remote"

                    if kw and kw not in title.lower():
                        continue
                    if loc and loc not in (job_location or "").lower() and not (remote_only and is_remote):
                        continue
                    if remote_only and not is_remote:
                        continue

                    jobs.append(NormalizedJob(
                        external_id=str(item.get("id")),
                        title=title,
                        company=site,
                        location=job_location,
                        remote=is_remote,
                        url=item.get("hostedUrl", ""),
                        description=item.get("descriptionPlain") or item.get("description"),
                        posted_at=None,
                        raw=item,
                    ))
                    if len(jobs) >= max_results:
                        break
        return jobs
