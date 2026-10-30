"""Convert each ATS's raw API response into the shared Job format."""

from datetime import datetime, timezone

from job_board_mcp.models import Job


def normalize_greenhouse(raw: dict, company: str) -> tuple[list[Job], list[str]]:
    """Return (jobs, warnings). Jobs missing an id, title, or URL are skipped with a warning."""

    warnings = []
    jobs = []

    for job in raw.get("jobs", []):

        # First try to get the job title, ID, and URL from the raw job data
        title = job.get("title", "")
        job_id = job.get("id", "")       
        url = job.get("absolute_url", "")

        if not title or not job_id or not url:
            warnings.append(f"Skipping job with missing fields: title={title}, job_id={job_id}, url={url}")
            continue

        if isinstance(job_id, int):
            job_id = str(job_id)

        location = job.get("location", {}).get("name", "")

        if "remote" in location.lower():
            remote = True
        else:
            remote = None

        date_str = job.get("first_published", "")

        if date_str:
            local_time = datetime.fromisoformat(date_str)
            posted_at = local_time.astimezone(timezone.utc)
        else:
            posted_at = None

        ats = "greenhouse"

        lanes = []

        normalized_job = Job(
            company = company,
            title = title,
            location = location,
            remote = remote,
            url = url,
            posted_at = posted_at,
            ats = ats,
            job_id = job_id,
            lanes = lanes
        )

        jobs.append(normalized_job)

    return jobs, warnings
        