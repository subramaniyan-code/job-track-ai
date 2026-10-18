from typing import Optional

import httpx

from .base import BaseConnector, NormalizedJob


class GreenhouseConnector(BaseConnector):
    """
    No API key required — reads the same public JSON feed the company's
    own careers page uses. credentials = {"board_tokens": "stripe,airbnb,figma"}
    (comma-separated Greenhouse board tokens for the companies you want to track).
    """
    source_name = "greenhouse"

    async def search(self, keywords: str, location: Optional[str], remote_only: bool, max_results: int) -> list[NormalizedJob]:
        tokens = [t.strip() for t in self.credentials.get("board_tokens", "").split(",") if t.strip()]
        if not tokens:
            return []

        jobs: list[NormalizedJob] = []
        kw = keywords.lower()
        loc = (location or "").lower()

        async with httpx.AsyncClient(timeout=20) as client:
            for token in tokens:
                if len(jobs) >= max_results:
                    break
                url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPError:
                    continue

                for item in data.get("jobs", []):
                    title = item.get("title", "")
                    job_location = (item.get("location") or {}).get("name", "")
                    is_remote = "remote" in job_location.lower()

                    if kw and kw not in title.lower():
                        continue
                    if loc and loc not in job_location.lower() and not (remote_only and is_remote):
                        continue
                    if remote_only and not is_remote:
                        continue

                    jobs.append(NormalizedJob(
                        external_id=str(item.get("id")),
                        title=title,
                        company=token,
                        location=job_location,
                        remote=is_remote,
                        url=item.get("absolute_url", ""),
                        description=item.get("content"),
                        posted_at=None,
                        raw=item,
                    ))
                    if len(jobs) >= max_results:
                        break
        return jobs
