import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from job_board_mcp.models import Job
from job_board_mcp.normalize import normalize_greenhouse, normalize_ashby

FIXTURES = Path(__file__).parent / "fixtures"


### Greenhouse Normalization Tests ###

@pytest.fixture
def greenhouse_raw():
    # Load fresh raw data from the fixture file for each test
    return json.loads((FIXTURES / "greenhouse_jobs.json").read_text(encoding="utf-8"))

def test_greenhouse_maps_fields(greenhouse_raw):
    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert warnings == []
    assert len(jobs) == 5
    assert jobs[0] == Job(
        company="Addepar",
        title="AddeGrad Program (2027) - Client Solutions Analyst",
        location="Salt Lake City, UT",
        remote=None,
        url="https://job-boards.greenhouse.io/addepar1/jobs/8815241002",
        posted_at=datetime(2026, 9, 16, 19, 27, 34, tzinfo=timezone.utc),
        ats="greenhouse",
        job_id="8815241002",
        lanes=[]
    )


def test_greenhouse_posted_at_is_utc(greenhouse_raw):
    jobs, _ = normalize_greenhouse(greenhouse_raw, "Addepar")
    # "2026-09-16T15:27:34-04:00" is 19:27:34 UTC. Checking the offset matters because
    # datetimes in different time zones compare equal when they're the same moment.
    assert all(job.posted_at.utcoffset() == timedelta(0) for job in jobs)


def test_greenhouse_job_id_is_string(greenhouse_raw):
    jobs, _ = normalize_greenhouse(greenhouse_raw, "Addepar")
    assert all(isinstance(job.job_id, str) for job in jobs)


def test_greenhouse_remote_only_known_from_location(greenhouse_raw):
    jobs, _ = normalize_greenhouse(greenhouse_raw, "Addepar")
    remote_by_location = {job.location: job.remote for job in jobs}
    assert remote_by_location["Remote, USA"] is True
    assert remote_by_location["New York, NY"] is None  # not False: the location doesn't say


def test_greenhouse_skips_job_without_title(greenhouse_raw):
    # A real entry with one field broken. The fixture file itself stays unedited.
    greenhouse_raw["jobs"][0]["title"] = ""

    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "8815241002" in warnings[0]  # the warning names the skipped job


def test_greenhouse_skips_job_without_id(greenhouse_raw):
    # A real entry with one field broken. The fixture file itself stays unedited.
    greenhouse_raw["jobs"][0]["id"] = ""

    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "8815241002" in warnings[0]  # the warning names the skipped job


def test_greenhouse_skips_job_without_url(greenhouse_raw):
    # A real entry with one field broken. The fixture file itself stays unedited.
    greenhouse_raw["jobs"][0]["absolute_url"] = ""

    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "8815241002" in warnings[0]  # the warning names the skipped job


def test_greenhouse_continues_without_location(greenhouse_raw):
    greenhouse_raw["jobs"][0]["location"] = {}

    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert len(jobs) == 5
    assert len(warnings) == 0


def test_greenhouse_skips_job_with_broken_date(greenhouse_raw):
    # A real entry with one field broken. The fixture file itself stays unedited.
    greenhouse_raw["jobs"][0]["first_published"] = "thrd67867vf"

    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "8815241002" in warnings[0]  # the warning names the skipped job




### Ashby Normalization Tests ###
@pytest.fixture
def ashby_raw():
    # Load fresh raw data from the fixture file for each test
        return json.loads((FIXTURES / "ashby_jobs.json").read_text(encoding="utf-8"))