"""Convert each ATS's raw API response into the shared Job format."""

from datetime import datetime, timezone

from job_board_mcp.lanes import matches, tokenize
from job_board_mcp.models import Job


def _job_label(
    job_id: str | int | None,
    title: str | None,
    url: str | None,
) -> str:
    """Return the best available identifier for a job warning."""
    if job_id:
        return f"job_id={job_id}"
    if title:
        return f"title={title}"
    if url:
        return f"url={url}"
    return "unknown job"


def _parse_iso_utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _remote_from_workplace_type(workplace_type: object) -> bool | None:
    if not isinstance(workplace_type, str):
        return None

    normalized = workplace_type.lower().replace("-", "")
    if normalized == "remote":
        return True
    if normalized in {"onsite", "hybrid"}:
        return False
    return None


def normalize_greenhouse(raw: dict, company: str) -> tuple[list[Job], list[str]]:
    """Return (jobs, warnings). Jobs missing an id, title, or URL are skipped with a warning."""

    warnings = []
    jobs = []

    for job in raw["jobs"]:

        # First try to get the job title, ID, and URL from the raw job data
        title = job.get("title", "")
        job_id = job.get("id", "")
        url = job.get("absolute_url", "")
        date_str = job.get("first_published", "")

        if not title or not job_id or not url or not date_str:
            warnings.append(
                f"Skipping job with missing fields: {_job_label(job_id, title, url)}"
            )
            continue

        posted_at = _parse_iso_utc(date_str)
        if posted_at is None:
            warnings.append(
                f"Skipping job with invalid date: {_job_label(job_id, title, url)}, "
                f"posted_at={date_str}"
            )
            continue

        job_id = str(job_id)
        location = (job.get("location") or {}).get("name", "")

        if matches(tokenize(location), "remote"):
            remote = True
        else:
            remote = None

        normalized_job = Job(
            company=company,
            title=title,
            location=location,
            remote=remote,
            url=url,
            posted_at=posted_at,
            ats="greenhouse",
            job_id=job_id,
        )

        jobs.append(normalized_job)

    return jobs, warnings


def normalize_ashby(raw: dict, company: str) -> tuple[list[Job], list[str]]:
    """Normalize Ashby jobs into the shared Job format."""
    warnings = []
    jobs = []

    for job in raw["jobs"]:
        if job.get("isListed") is False:
            continue

        title = job.get("title", "")
        job_id = job.get("id", "")
        url = job.get("jobUrl", "")
        date_str = job.get("publishedAt", "")

        if not title or not job_id or not url or not date_str:
            warnings.append(
                f"Skipping job with missing fields: {_job_label(job_id, title, url)}"
            )
            continue

        posted_at = _parse_iso_utc(date_str)
        if posted_at is None:
            warnings.append(
                f"Skipping job with invalid date: {_job_label(job_id, title, url)}, "
                f"posted_at={date_str}"
            )
            continue

        secondary_locations = job.get("secondaryLocations") or []
        locations = [job.get("location") or ""]
        locations.extend(
            secondary.get("location", "")
            for secondary in secondary_locations
            if isinstance(secondary, dict) and secondary.get("location")
        )
        location = "; ".join(value for value in locations if value)

        remote = _remote_from_workplace_type(job.get("workplaceType"))
        if remote is None and job.get("workplaceType") is None:
            is_remote = job.get("isRemote")
            remote = is_remote if isinstance(is_remote, bool) else None

        jobs.append(
            Job(
                company=company,
                title=title,
                location=location,
                remote=remote,
                url=url,
                posted_at=posted_at,
                ats="ashby",
                job_id=str(job_id),
            )
        )

    return jobs, warnings


def normalize_lever(raw: dict, company: str) -> tuple[list[Job], list[str]]:
    """Normalize Lever jobs into the shared Job format."""
    warnings = []
    jobs = []

    for job in raw:
        title = job.get("text", "")
        job_id = job.get("id", "")
        url = job.get("hostedUrl", "")
        created_at = job.get("createdAt")

        if not title or not job_id or not url or created_at is None or created_at == "":
            warnings.append(f"Skipping job with missing fields: {_job_label(job_id, title, url)}")
            continue

        if isinstance(created_at, bool) or not isinstance(created_at, (int, float)):
            warnings.append(
                f"Skipping job with invalid date: {_job_label(job_id, title, url)}, "
                f"createdAt={created_at}"
            )
            continue

        try:
            posted_at = datetime.fromtimestamp(
                created_at / 1000, tz=timezone.utc
            )
        except (OverflowError, OSError, ValueError):
            warnings.append(
                f"Skipping job with invalid date: {_job_label(job_id, title, url)}, "
                f"createdAt={created_at}"
            )
            continue

        categories = job.get("categories") or {}
        all_locations = categories.get("allLocations") or []
        location = "; ".join(value for value in all_locations if value)

        jobs.append(
            Job(
                company=company,
                title=title,
                location=location,
                remote=_remote_from_workplace_type(job.get("workplaceType")),
                url=url,
                posted_at=posted_at,
                ats="lever",
                job_id=str(job_id),
            )
        )

    return jobs, warnings