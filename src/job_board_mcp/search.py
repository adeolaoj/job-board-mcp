"""Turn fetched job boards into a filtered, sorted search response. No network, no MCP."""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from job_board_mcp.config import Company
from job_board_mcp.lanes import classify, matches, tokenize
from job_board_mcp.models import Job
from job_board_mcp.normalize import normalize_ashby, normalize_greenhouse, normalize_lever

NORMALIZERS = {"greenhouse": normalize_greenhouse, "lever": normalize_lever, "ashby": normalize_ashby}


@dataclass(frozen=True)
class SearchFilters:
    lane: str | None = None
    keywords: list[str] | None = None    # match ANY, on titles
    locations: list[str] | None = None   # match ANY, on the location string
    remote: bool | None = None           # uses job.remote, not the location text
    posted_within_days: int | None = None
    limit: int = 25

    def __post_init__(self):
        # A negative slice like jobs[:-1] would silently drop jobs instead of capping them.
        if self.limit < 0:
            raise ValueError(f"limit must be 0 or more, got {self.limit}")
        if self.posted_within_days is not None and self.posted_within_days < 0:
            raise ValueError(f"posted_within_days must be 0 or more, got {self.posted_within_days}")


def check_lane(lane: str | None, lanes: dict) -> None:
    """Raise ValueError listing the valid lanes if lane isn't one of them. None is allowed."""
    valid = lanes["lanes"]
    if lane is not None and lane not in valid:
        raise ValueError(f"Invalid lane: {lane}. Valid lanes are: {', '.join(valid)}")


def select_companies(
    all_companies: list[Company], names: list[str] | None
) -> tuple[list[Company], list[str]]:
    """Return (companies to search, errors). None means all. Names ignore case and surrounding spaces; repeats are dropped."""
    if names is None:
        return list(all_companies), []

    # Create a dictionary mapping casefolded company names to actual company objects
    by_name = {company.name.casefold(): company for company in all_companies}
    selected = []
    errors = []
    seen = set()

    for name in names:
        key = name.strip().casefold()
        if key in seen:
            continue
        seen.add(key)

        company = by_name.get(key)
        if company is None:
            errors.append(f"Unknown company: {name}")
        else:
            selected.append(company)
    return selected, errors


def _passes(job: Job, filters: SearchFilters, now: datetime) -> bool:
    """True if the job satisfies every filter that is set. Empty keyword/location lists don't filter."""
    if filters.lane is not None and filters.lane not in job.lanes:
        return False

    if filters.keywords:
        title_tokens = tokenize(job.title)
        if not any(matches(title_tokens, keyword) for keyword in filters.keywords):
            return False

    if filters.locations:
        location_tokens = tokenize(job.location)
        if not any(matches(location_tokens, location) for location in filters.locations):
            return False

    # remote=True keeps only True; remote=False keeps only False. Unknown (None) never matches.
    if filters.remote is not None and job.remote is not filters.remote:
        return False

    if filters.posted_within_days is not None:
        if now - job.posted_at > timedelta(days=filters.posted_within_days):
            return False

    return True


def _format_job(job: Job) -> dict:
    return asdict(job) | {"posted_at": job.posted_at.date().isoformat()}


def build_search_response(
    companies: list[Company],
    results: list[Any],
    lanes: dict,
    filters: SearchFilters,
    now: datetime,
) -> dict:
    """Normalize, classify, filter, sort newest first, and format. results[i] belongs to companies[i]."""
    # Job dates are UTC-aware; subtracting them from a naive now raises TypeError mid-search.
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    errors = []
    warnings = []
    matched = []

    # strict=True: a length mismatch means the caller paired results wrongly, so fail loudly.
    for company, result in zip(companies, results, strict=True):
        if isinstance(result, Exception):
            errors.append(f"{company.name}: {result}")
            continue

        # Looked up outside the try so an unsupported ATS isn't reported as a bad response.
        normalize = NORMALIZERS.get(company.ats)
        if normalize is None:
            errors.append(f"{company.name}: unsupported ATS {company.ats!r}")
            continue

        try:
            jobs, company_warnings = normalize(result, company.name)
        except (KeyError, TypeError, AttributeError):
            # The board answered with JSON, but not in the shape this ATS normally uses.
            errors.append(f"{company.name}: unexpected {company.ats} response format")
            continue

        warnings.extend(f"{company.name}: {warning}" for warning in company_warnings)

        for job in jobs:
            job.lanes = classify(job.title, lanes)
            if _passes(job, filters, now):
                matched.append(job)

    matched.sort(key=lambda job: job.posted_at, reverse=True)

    return {
        "total_matches": len(matched),
        "jobs": [_format_job(job) for job in matched[: filters.limit]],
        "errors": errors,
        "warnings": warnings,
    }
