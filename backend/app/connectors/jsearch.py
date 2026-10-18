from datetime import datetime
from typing import Optional

import httpx

from .base import BaseConnector, NormalizedJob


class JSearchConnector(BaseConnector):
    """
    RapidAPI's JSearch — aggregates Google Jobs (which itself pulls from
    Indeed, LinkedIn, ZipRecruiter, etc.) behind one API. Free tier available.
    Get a key at https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
    credentials = {"rapidapi_key": "..."}
    """
    source_name = "jsearch"

    async def search(self, keywords: str, location: Optional[str], remote_only: bool, max_results: int) -> list[NormalizedJob]:
        key = self.credentials.get("rapidapi_key")
        if not key:
            return []

        query = keywords if not location else f"{keywords} in {location}"
        params = {"query": query, "page": "1", "num_pages": "1"}
        if remote_only:
            params["remote_jobs_only"] = "true"

        headers = {
            "X-RapidAPI-Key": key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get("https://jsearch.p.rapidapi.com/search", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        jobs = []
        for item in data.get("data", [])[:max_results]:
            posted = None
            if item.get("job_posted_at_datetime_utc"):
                try:
                    posted = datetime.fromisoformat(item["job_posted_at_datetime_utc"].replace("Z", "+00:00"))
                except ValueError:
                    posted = None
            loc = ", ".join(filter(None, [item.get("job_city"), item.get("job_country")]))
            jobs.append(NormalizedJob(
                external_id=item.get("job_id", ""),
                title=item.get("job_title", ""),
                company=item.get("employer_name"),
                location=loc,
                remote=bool(item.get("job_is_remote")),
                url=item.get("job_apply_link", ""),
                description=item.get("job_description"),
                posted_at=posted,
                raw=item,
            ))
        return jobs
