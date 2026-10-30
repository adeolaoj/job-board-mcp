"""Convert each ATS's raw API response into the shared Job format."""

from datetime import datetime, timezone

from job_board_mcp.lanes import matches, tokenize
from job_board_mcp.models import Job


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
            warnings.append(f"Skipping job with missing fields: title={title}, job_id={job_id}, url={url}, posted_at={date_str}")
            continue

        try:
            local_time = datetime.fromisoformat(date_str)
        except ValueError:
            warnings.append(f"Skipping job with invalid date: job_id={job_id}, posted_at={date_str}")
            continue
        
        posted_at = local_time.astimezone(timezone.utc)

        job_id = str(job_id)
        location = (job.get("location") or {}).get("name", "")

        if matches(tokenize(location), "remote"):
            remote = True
        else:
            remote = None

        ats = "greenhouse"

        normalized_job = Job(
            company = company,
            title = title,
            location = location,
            remote = remote,
            url = url,
            posted_at = posted_at,
            ats = ats,
            job_id = job_id
        )

        jobs.append(normalized_job)

    return jobs, warnings
        