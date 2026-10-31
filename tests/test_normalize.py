import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from job_board_mcp.models import Job
from job_board_mcp.normalize import (
    description_ashby,
    description_greenhouse,
    description_lever,
    normalize_ashby,
    normalize_greenhouse,
    normalize_lever,
)

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
    assert "AddeGrad Program (2027) - Client Solutions Analyst" in warnings[0]


def test_greenhouse_skips_job_without_url(greenhouse_raw):
    # A real entry with one field broken. The fixture file itself stays unedited.
    greenhouse_raw["jobs"][0]["absolute_url"] = ""

    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "8815241002" in warnings[0]  # the warning names the skipped job


def test_greenhouse_continues_without_location(greenhouse_raw):
    greenhouse_raw["jobs"][0]["location"] = None

    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert len(jobs) == 5
    assert warnings == []


def test_greenhouse_skips_job_without_date(greenhouse_raw):
    greenhouse_raw["jobs"][0].pop("first_published")

    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "8815241002" in warnings[0]


def test_greenhouse_skips_job_with_broken_date(greenhouse_raw):
    # A real entry with one field broken. The fixture file itself stays unedited.
    greenhouse_raw["jobs"][0]["first_published"] = "thrd67867vf"

    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "8815241002" in warnings[0]  # the warning names the skipped job


def test_greenhouse_treats_naive_date_as_utc(greenhouse_raw):
    greenhouse_raw["jobs"][0]["first_published"] = "2026-09-16T15:27:34"

    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert warnings == []
    assert jobs[0].posted_at == datetime(2026, 9, 16, 15, 27, 34, tzinfo=timezone.utc)


def test_greenhouse_skips_job_with_non_string_date(greenhouse_raw):
    greenhouse_raw["jobs"][0]["first_published"] = 1760000000

    jobs, warnings = normalize_greenhouse(greenhouse_raw, "Addepar")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "invalid date" in warnings[0]
    assert "8815241002" in warnings[0]




### Ashby Normalization Tests ###
@pytest.fixture
def ashby_raw():
    # Load fresh raw data from the fixture file for each test
    return json.loads((FIXTURES / "ashby_jobs.json").read_text(encoding="utf-8"))


def test_ashby_maps_fields(ashby_raw):
    jobs, warnings = normalize_ashby(ashby_raw, "Deepgram")

    assert warnings == []
    assert len(jobs) == 5
    assert jobs[0] == Job(
        company="Deepgram",
        title="Research Staff, Voice AI Foundations",
        location="USA - Remote; San Francisco, CA; Ann Arbor, Michigan",
        remote=True,
        url="https://jobs.ashbyhq.com/deepgram/7cf277bc-a192-4007-a77a-fafbf8276a5e",
        posted_at=datetime(2026, 8, 23, 17, 43, 40, 888000, tzinfo=timezone.utc),
        ats="ashby",
        job_id="7cf277bc-a192-4007-a77a-fafbf8276a5e",
        lanes=[],
    )


def test_ashby_posted_at_is_utc(ashby_raw):
    jobs, _ = normalize_ashby(ashby_raw, "Deepgram")
    assert all(job.posted_at.utcoffset() == timedelta(0) for job in jobs)


def test_ashby_job_id_is_string(ashby_raw):
    jobs, _ = normalize_ashby(ashby_raw, "Deepgram")
    assert all(isinstance(job.job_id, str) for job in jobs)


def test_ashby_remote_prefers_workplace_type_to_is_remote(ashby_raw):
    jobs, _ = normalize_ashby(ashby_raw, "Deepgram")
    remote_by_title = {job.title: job.remote for job in jobs}

    assert remote_by_title["Research Staff, Voice AI Foundations"] is True
    assert remote_by_title["Forward-Deployed Engineer (FDE), Strategic Accounts"] is False
    assert remote_by_title["Senior Forward-Deployed Engineer, Federal"] is None
    assert remote_by_title["Executive Coordinator"] is False


def test_ashby_remote_falls_back_to_is_remote_when_workplace_type_is_missing(ashby_raw):
    ashby_raw["jobs"][0]["workplaceType"] = None

    jobs, _ = normalize_ashby(ashby_raw, "Deepgram")

    assert jobs[0].remote is True


def test_ashby_skips_job_without_title(ashby_raw):
    ashby_raw["jobs"][0]["title"] = ""

    jobs, warnings = normalize_ashby(ashby_raw, "Deepgram")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "7cf277bc-a192-4007-a77a-fafbf8276a5e" in warnings[0]


def test_ashby_skips_job_without_id(ashby_raw):
    ashby_raw["jobs"][0]["id"] = ""

    jobs, warnings = normalize_ashby(ashby_raw, "Deepgram")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "Research Staff, Voice AI Foundations" in warnings[0]


def test_ashby_skips_job_without_url(ashby_raw):
    ashby_raw["jobs"][0]["jobUrl"] = ""

    jobs, warnings = normalize_ashby(ashby_raw, "Deepgram")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "7cf277bc-a192-4007-a77a-fafbf8276a5e" in warnings[0]


def test_ashby_continues_without_location(ashby_raw):
    ashby_raw["jobs"][0]["location"] = None

    jobs, warnings = normalize_ashby(ashby_raw, "Deepgram")

    assert len(jobs) == 5
    assert warnings == []


def test_ashby_skips_job_with_broken_date(ashby_raw):
    ashby_raw["jobs"][0]["publishedAt"] = "thrd67867vf"

    jobs, warnings = normalize_ashby(ashby_raw, "Deepgram")

    assert len(jobs) == 4
    assert len(warnings) == 1
    assert "7cf277bc-a192-4007-a77a-fafbf8276a5e" in warnings[0]


def test_ashby_skips_unlisted_job(ashby_raw):
    ashby_raw["jobs"][0]["isListed"] = False

    jobs, warnings = normalize_ashby(ashby_raw, "Deepgram")

    assert len(jobs) == 4
    assert warnings == []


### Lever Normalization Tests ###
@pytest.fixture
def lever_raw():
    # Load fresh raw data from the fixture file for each test
    return json.loads((FIXTURES / "lever_jobs.json").read_text(encoding="utf-8"))


def test_lever_maps_fields(lever_raw):
    jobs, warnings = normalize_lever(lever_raw, "Zoox")

    assert warnings == []
    assert len(jobs) == 4
    assert jobs[0] == Job(
        company="Zoox",
        title="Director, Corporate Security",
        location="Foster City, CA",
        remote=False,
        url="https://jobs.lever.co/zoox/8af192a0-9ee4-45de-a241-f373cb2ef71c",
        posted_at=datetime(2026, 2, 17, 20, 12, 2, 548000, tzinfo=timezone.utc),
        ats="lever",
        job_id="8af192a0-9ee4-45de-a241-f373cb2ef71c",
        lanes=[],
    )


def test_lever_posted_at_is_utc(lever_raw):
    jobs, _ = normalize_lever(lever_raw, "Zoox")
    assert all(job.posted_at.utcoffset() == timedelta(0) for job in jobs)


def test_lever_job_id_is_string(lever_raw):
    jobs, _ = normalize_lever(lever_raw, "Zoox")
    assert all(isinstance(job.job_id, str) for job in jobs)


def test_lever_remote_uses_workplace_type(lever_raw):
    lever_raw[0]["workplaceType"] = "remote"
    lever_raw[1]["workplaceType"] = "on-site"

    jobs, _ = normalize_lever(lever_raw, "Zoox")
    remote_by_title = {job.title: job.remote for job in jobs}

    assert remote_by_title["Director, Corporate Security"] is True
    assert remote_by_title["Director, Go-To-Market Strategy"] is False


def test_lever_joins_all_locations(lever_raw):
    jobs, _ = normalize_lever(lever_raw, "Zoox")
    job_by_id = {job.job_id: job for job in jobs}

    assert job_by_id["a30574c9-8ef3-408f-bc85-39aad54ad115"].location == (
        "Foster City, CA; Seattle, WA; Boston, MA"
    )
    assert job_by_id["a30574c9-8ef3-408f-bc85-39aad54ad115"].remote is False


def test_lever_skips_job_without_title(lever_raw):
    lever_raw[0]["text"] = ""

    jobs, warnings = normalize_lever(lever_raw, "Zoox")

    assert len(jobs) == 3
    assert len(warnings) == 1
    assert "8af192a0-9ee4-45de-a241-f373cb2ef71c" in warnings[0]


def test_lever_skips_job_without_id(lever_raw):
    lever_raw[0]["id"] = ""

    jobs, warnings = normalize_lever(lever_raw, "Zoox")

    assert len(jobs) == 3
    assert len(warnings) == 1
    assert "Director, Corporate Security" in warnings[0]


def test_lever_skips_job_without_url(lever_raw):
    lever_raw[0]["hostedUrl"] = ""

    jobs, warnings = normalize_lever(lever_raw, "Zoox")

    assert len(jobs) == 3
    assert len(warnings) == 1
    assert "8af192a0-9ee4-45de-a241-f373cb2ef71c" in warnings[0]


def test_lever_continues_without_location(lever_raw):
    lever_raw[0]["categories"]["allLocations"] = None

    jobs, warnings = normalize_lever(lever_raw, "Zoox")

    assert len(jobs) == 4
    assert warnings == []


def test_lever_skips_job_with_broken_date(lever_raw):
    lever_raw[0]["createdAt"] = "thrd67867vf"

    jobs, warnings = normalize_lever(lever_raw, "Zoox")

    assert len(jobs) == 3
    assert len(warnings) == 1
    assert "8af192a0-9ee4-45de-a241-f373cb2ef71c" in warnings[0]


### Description Tests ###

@pytest.fixture
def greenhouse_detail():
    return json.loads((FIXTURES / "greenhouse_job_detail.json").read_text(encoding="utf-8"))


@pytest.fixture
def lever_detail():
    return json.loads((FIXTURES / "lever_job_detail.json").read_text(encoding="utf-8"))


def test_greenhouse_description_unescapes_both_layers(greenhouse_detail):
    text = description_greenhouse(greenhouse_detail)

    assert text.startswith("Who We Are")
    assert "<" not in text
    assert "&lt;" not in text
    assert "&amp;" not in text
    assert "R&D" in text
    assert "- Provide hands-on support" in text


def test_greenhouse_description_missing_content_is_empty(greenhouse_detail):
    del greenhouse_detail["content"]

    assert description_greenhouse(greenhouse_detail) == ""


def test_lever_description_includes_lists_and_additional(lever_detail):
    text = description_lever(lever_detail)

    assert text.startswith("The Program Management Office (PMO) at Zoox")
    assert "<li>" not in text
    assert "In this Role, You Will...\n- Drive Clarity and Unity" in text
    for section in lever_detail["lists"]:
        assert section["text"] in text
    assert "About Zoox" in text


def test_lever_description_keeps_section_order(lever_detail):
    text = description_lever(lever_detail)

    description_at = text.index("The Program Management Office")
    first_list_at = text.index("In this Role, You Will...")
    last_list_at = text.index("Bonus Qualifications")
    additional_at = text.index("About Zoox")
    assert description_at < first_list_at < last_list_at < additional_at


def test_lever_description_without_lists(lever_detail):
    lever_detail["lists"] = None

    text = description_lever(lever_detail)

    assert "In this Role, You Will..." not in text
    assert text.startswith("The Program Management Office")
    assert "About Zoox" in text


def test_lever_description_missing_everything_is_empty():
    assert description_lever({}) == ""


def test_ashby_description_uses_description_plain(ashby_raw):
    job = ashby_raw["jobs"][0]

    text = description_ashby(job)

    assert text == job["descriptionPlain"].strip()
    assert text.startswith("COMPANY OVERVIEW")


def test_ashby_description_missing_is_empty(ashby_raw):
    job = ashby_raw["jobs"][0]
    job["descriptionPlain"] = None

    assert description_ashby(job) == ""
