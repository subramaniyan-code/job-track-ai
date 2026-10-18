from datetime import datetime
from typing import Optional

import httpx

from .base import BaseConnector, NormalizedJob


class AdzunaConnector(BaseConnector):
    """
    Free API — get an App ID + App Key at https://developer.adzuna.com/
    credentials = {"app_id": "...", "app_key": "...", "country": "in"}
    """
    source_name = "adzuna"

    async def search(self, keywords: str, location: Optional[str], remote_only: bool, max_results: int) -> list[NormalizedJob]:
        app_id = self.credentials.get("app_id")
        app_key = self.credentials.get("app_key")
        country = self.credentials.get("country", "in")
        if not app_id or not app_key:
            return []

        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": min(max_results, 50),
            "what": keywords,
            "content-type": "application/json",
        }
        if location:
            params["where"] = location

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        jobs = []
        for item in data.get("results", []):
            desc = item.get("description", "") or ""
            is_remote = remote_only or "remote" in desc.lower() or "remote" in (item.get("location", {}).get("display_name", "") or "").lower()
            posted = None
            if item.get("created"):
                try:
                    posted = datetime.fromisoformat(item["created"].replace("Z", "+00:00"))
                except ValueError:
                    posted = None
            jobs.append(NormalizedJob(
                external_id=str(item.get("id")),
                title=item.get("title", "").strip(),
                company=(item.get("company") or {}).get("display_name"),
                location=(item.get("location") or {}).get("display_name"),
                remote=is_remote,
                url=item.get("redirect_url", ""),
                description=desc,
                posted_at=posted,
                raw=item,
            ))
        return jobs
