"""
Every job-source connector implements this interface. To add a new API
(e.g. USAJobs, RemoteOK, Ashby), drop a new file in this folder subclassing
BaseConnector and register it in registry.py — nothing else in the app
needs to change.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class NormalizedJob:
    """The common shape every connector must translate its API's response into."""

    def __init__(
        self,
        external_id: str,
        title: str,
        company: Optional[str],
        location: Optional[str],
        remote: bool,
        url: str,
        description: Optional[str],
        posted_at: Optional[datetime],
        raw: dict,
    ):
        self.external_id = external_id
        self.title = title
        self.company = company
        self.location = location
        self.remote = remote
        self.url = url
        self.description = description
        self.posted_at = posted_at
        self.raw = raw


class BaseConnector(ABC):
    source_name: str = "base"

    def __init__(self, credentials: dict):
        self.credentials = credentials or {}

    @abstractmethod
    async def search(self, keywords: str, location: Optional[str], remote_only: bool, max_results: int) -> list[NormalizedJob]:
        """Return a list of NormalizedJob for the given query."""
        raise NotImplementedError
