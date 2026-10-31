"""Fetch job board JSON over HTTP, with caching."""

import asyncio
from typing import Any

import httpx

from job_board_mcp.cache import TTLCache
from job_board_mcp.config import Company

USER_AGENT = "job-board-mcp/0.1 (+https://github.com/adeolaoj/job-board-mcp)"
CACHE_TTL_SECONDS = 15 * 60
_CACHE_MISS = object()


class FetchError(Exception):
    """A company's board couldn't be fetched: network error, bad status, or non-JSON body."""


def make_client() -> httpx.AsyncClient:
    """Create an HTTP client with standard headers and a 10-second request timeout."""
    return httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=10.0)


def list_url(company: Company) -> str:
    """ Return the URL for the company's job board listing."""
    if company.ats == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{company.slug}/jobs"
    if company.ats == "lever":
        return f"https://api.lever.co/v0/postings/{company.slug}?mode=json"
    if company.ats == "ashby":
        return f"https://api.ashbyhq.com/posting-api/job-board/{company.slug}"

    raise ValueError(f"Unsupported ATS: {company.ats}")


def detail_url(company: Company, job_id: str) -> str:
    """Raises ValueError for Ashby, which has no public detail endpoint."""
    if company.ats == "ashby":
        raise ValueError(f"Ashby does not have a public detail endpoint for job {job_id}")

    if company.ats == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{company.slug}/jobs/{job_id}"
    if company.ats == "lever":
        return f"https://api.lever.co/v0/postings/{company.slug}/{job_id}?mode=json"

    raise ValueError(f"Unsupported ATS: {company.ats}")


class Fetcher:
    def __init__(self, client: httpx.AsyncClient, cache: TTLCache):
        self._client = client
        self._cache = cache

    async def fetch_json(self, url: str) -> Any:
        """Return parsed JSON for url, from the cache if fresh. Raises FetchError on any failure."""

        cached = self._cache.get(url, _CACHE_MISS)
        if cached is not _CACHE_MISS:
            return cached

        # Otherwise, fetch the json and store in the cache

        try:
            response = await self._client.get(url)
        except httpx.HTTPError as exc:
            raise FetchError(
                f"Failed to fetch {url} ({type(exc).__name__})"
            ) from exc

        if response.status_code != 200:
            raise FetchError(f"Failed to fetch {url}: {response.status_code}")

        # Check if response is valid JSON
        try:
            data = response.json()
        except ValueError as exc:
            raise FetchError(f"Response from {url} is not valid JSON") from exc

        self._cache.set(url, data)

        return data
    

    async def fetch_boards(self, companies: list[Company]) -> list[Any | Exception]:
        """Fetch every company's list URL concurrently. Failures come back as exceptions, in order."""

        async def fetch_one(company: Company) -> Any | Exception:
            try:
                return await self.fetch_json(list_url(company))
            except FetchError as exc:
                return exc
        
        return await asyncio.gather(*(fetch_one(company) for company in companies))