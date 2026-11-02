import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from job_board_mcp.config import Company
from job_board_mcp.fetch import FetchError
from job_board_mcp.lanes import load_lanes
from job_board_mcp.search import SearchFilters, build_search_response, check_lane, select_companies

FIXTURES = Path(__file__).parent / "fixtures"
LANES_PATH = Path(__file__).parent.parent / "config" / "lanes.yaml"

ADDEPAR = Company(name="Addepar", ats="greenhouse", slug="addepar1")
ZOOX = Company(name="Zoox", ats="lever", slug="zoox")
DEEPGRAM = Company(name="Deepgram", ats="ashby", slug="deepgram")
SIERRA = Company(name="Sierra", ats="ashby", slug="sierra")

# A fixed "now" so date filters give the same answer every day the tests run.
NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lanes():
    return load_lanes(LANES_PATH)


@pytest.fixture
def results():
    # What fetch_boards would return for [ADDEPAR, ZOOX, DEEPGRAM]: 14 jobs in total.
    return [
        load_fixture("greenhouse_jobs.json"),
        load_fixture("lever_jobs.json"),
        load_fixture("ashby_jobs.json"),
    ]


def search(results, lanes, **filters):
    return build_search_response(
        [ADDEPAR, ZOOX, DEEPGRAM], results, lanes, SearchFilters(**filters), NOW
    )


def titles(response):
    return [job["title"] for job in response["jobs"]]


# --- No filters ---

def test_returns_every_job_newest_first(results, lanes):
    response = search(results, lanes)

    assert response["total_matches"] == 14
    assert len(response["jobs"]) == 14
    assert response["jobs"][0]["title"] == "Product Manager - Early Career, AI Platform"
    assert response["jobs"][-1]["title"] == "Director, Corporate Security"
    dates = [job["posted_at"] for job in response["jobs"]]
    assert dates == sorted(dates, reverse=True)


def test_job_format(results, lanes):
    job = search(results, lanes)["jobs"][0]

    assert job == {
        "company": "Addepar",
        "title": "Product Manager - Early Career, AI Platform",
        "location": "New York, NY",
        "remote": None,
        "url": "https://job-boards.greenhouse.io/addepar1/jobs/8910404002",
        "posted_at": "2026-10-23",
        "ats": "greenhouse",
        "job_id": "8910404002",
        "lanes": ["pm", "new_grad"],
    }


def test_limit_caps_jobs_but_not_total(results, lanes):
    response = search(results, lanes, limit=3)

    assert len(response["jobs"]) == 3
    assert response["total_matches"] == 14


# --- Lane ---

def test_lane_deployment(results, lanes):
    assert titles(search(results, lanes, lane="deployment")) == [
        "Software Engineer - Customer Facing Applied AI",
        "Forward-Deployed Engineer (FDE), Strategic Accounts",
        "Customer Success Engineer (Scaled)",
    ]


def test_lane_new_grad(results, lanes):
    assert titles(search(results, lanes, lane="new_grad")) == [
        "Product Manager - Early Career, AI Platform",
        "AddeGrad Program (2027) - Client Solutions Analyst",
        "AddeGrad Program (2027) - Client Solutions Analyst",
    ]


def test_unknown_lane_lists_valid_lanes(lanes):
    with pytest.raises(ValueError) as excinfo:
        check_lane("product", lanes)

    message = str(excinfo.value)
    assert "product" in message
    for lane in ("deployment", "pm", "new_grad"):
        assert lane in message


def test_no_lane_is_valid(lanes):
    check_lane(None, lanes)  # must not raise


# --- Keywords, locations, remote, date ---

def test_keywords_match_any_and_ignore_lanes(results, lanes):
    # Keywords search titles directly, so excluded titles (Senior...) still match.
    assert titles(search(results, lanes, keywords=["forward deployed", "applied ai"])) == [
        "Software Engineer - Customer Facing Applied AI",
        "Forward-Deployed Engineer (FDE), Strategic Accounts",
        "Senior Forward-Deployed Engineer, Federal",
    ]


def test_locations_match_any_secondary_location_too(results, lanes):
    # "New York City, NY" is one of the FDE job's secondary locations.
    assert titles(search(results, lanes, locations=["nyc", "new york"])) == [
        "Product Manager - Early Career, AI Platform",
        "Forward-Deployed Engineer (FDE), Strategic Accounts",
    ]


def test_remote_true_uses_structured_field(results, lanes):
    assert titles(search(results, lanes, remote=True)) == [
        "Research Staff, Voice AI Foundations",
        "Customer Success Engineer (Scaled)",
        "Sr. Account Executive - Enterprise",
    ]


def test_posted_within_days(results, lanes):
    # NOW is Oct 29: Oct 23 and Oct 22 are within 7 days, Oct 9 is not.
    assert titles(search(results, lanes, posted_within_days=7)) == [
        "Product Manager - Early Career, AI Platform",
        "Senior Staff/Principal Software Engineer - GPU System Software, Onboard Execution",
    ]


def test_filters_combine(results, lanes):
    assert titles(search(results, lanes, lane="deployment", remote=True)) == [
        "Customer Success Engineer (Scaled)",
    ]


def test_lane_and_keywords_combine(results, lanes):
    # The Senior FDE matches the keyword but is excluded from every lane.
    assert titles(search(results, lanes, lane="deployment", keywords=["forward deployed"])) == [
        "Forward-Deployed Engineer (FDE), Strategic Accounts",
    ]


def test_remote_false_skips_unknown_and_remote(results, lanes):
    response = search(results, lanes, remote=False)

    assert response["total_matches"] == 6
    assert all(job["remote"] is False for job in response["jobs"])


def test_keywords_match_whole_words_not_substrings(results, lanes):
    assert search(results, lanes, keywords=["product man"])["total_matches"] == 0


def test_empty_keyword_and_location_lists_do_not_filter(results, lanes):
    assert search(results, lanes, keywords=[], locations=[])["total_matches"] == 14


def test_posted_within_days_includes_the_boundary(results, lanes):
    # The PM job was first published 2026-10-23T09:43:19-04:00; exactly 6 days later still counts.
    posted_at = datetime(2026, 10, 23, 13, 43, 19, tzinfo=timezone.utc)
    response = build_search_response(
        [ADDEPAR], results[:1], lanes, SearchFilters(posted_within_days=6), posted_at + timedelta(days=6)
    )

    assert titles(response) == ["Product Manager - Early Career, AI Platform"]


def test_limit_zero_returns_no_jobs_but_counts_matches(results, lanes):
    response = search(results, lanes, limit=0)

    assert response["jobs"] == []
    assert response["total_matches"] == 14


@pytest.mark.parametrize("field", ["limit", "posted_within_days"])
def test_negative_numbers_are_rejected(field):
    with pytest.raises(ValueError, match=field):
        SearchFilters(**{field: -1})


# --- Errors and warnings ---

def test_failed_company_goes_in_errors_and_others_still_return(results, lanes):
    response = build_search_response(
        [ADDEPAR, ZOOX, DEEPGRAM, SIERRA],
        results + [FetchError("https://api.ashbyhq.com/posting-api/job-board/sierra returned 404")],
        lanes,
        SearchFilters(),
        NOW,
    )

    assert response["total_matches"] == 14
    assert len(response["errors"]) == 1
    assert response["errors"][0].startswith("Sierra:")


def test_normalizer_warnings_name_the_company(results, lanes):
    results[0]["jobs"][0]["title"] = ""

    response = search(results, lanes)

    assert response["total_matches"] == 13
    assert len(response["warnings"]) == 1
    assert response["warnings"][0].startswith("Addepar:")


def test_clean_run_has_no_errors_or_warnings(results, lanes):
    response = search(results, lanes)

    assert response["errors"] == []
    assert response["warnings"] == []


def test_malformed_payload_goes_in_errors_and_others_still_return(results, lanes):
    # Greenhouse returns {"jobs": [...]}; a bare list means something upstream changed.
    results[0] = []

    response = search(results, lanes)

    assert response["total_matches"] == 9
    assert len(response["errors"]) == 1
    assert response["errors"][0].startswith("Addepar:")


def test_bad_job_fields_do_not_crash_the_search(results, lanes):
    results[0]["jobs"][0]["title"] = 123
    results[0]["jobs"][1]["location"] = {"name": None}

    response = search(results, lanes, locations=["new york"])

    assert titles(response) == [
        "Product Manager - Early Career, AI Platform",
        "Forward-Deployed Engineer (FDE), Strategic Accounts",
    ]
    assert len(response["warnings"]) == 1


def test_unsupported_ats_goes_in_errors(lanes):
    response = build_search_response(
        [Company(name="Acme", ats="workday", slug="acme")], [{"jobs": []}], lanes, SearchFilters(), NOW
    )

    assert response["errors"] == ["Acme: unsupported ATS 'workday'"]


def test_naive_now_is_rejected(results, lanes):
    with pytest.raises(ValueError, match="timezone"):
        build_search_response(
            [ADDEPAR, ZOOX, DEEPGRAM], results, lanes, SearchFilters(), datetime(2026, 10, 29)
        )


@pytest.mark.parametrize("keyword", ["", "   ", "--"])
def test_keyword_with_no_words_matches_nothing(results, lanes, keyword):
    assert search(results, lanes, keywords=[keyword])["total_matches"] == 0


def test_mismatched_companies_and_results_raise(results, lanes):
    with pytest.raises(ValueError):
        build_search_response([ADDEPAR, ZOOX], results, lanes, SearchFilters(), NOW)


def test_lane_config_keys_are_not_lanes(lanes):
    for key in ("lanes", "exclude"):
        with pytest.raises(ValueError):
            check_lane(key, lanes)


def test_known_lane_is_valid(lanes):
    check_lane("pm", lanes)  # must not raise


# --- Choosing companies ---

def test_select_companies_ignores_case():
    selected, errors = select_companies([ADDEPAR, ZOOX], ["addepar"])

    assert selected == [ADDEPAR]
    assert errors == []


def test_select_companies_reports_unknown_names_and_keeps_going():
    selected, errors = select_companies([ADDEPAR, ZOOX], ["Zoox", "Nope"])

    assert selected == [ZOOX]
    assert len(errors) == 1
    assert "Nope" in errors[0]


def test_select_companies_none_means_all():
    assert select_companies([ADDEPAR, ZOOX], None) == ([ADDEPAR, ZOOX], [])


def test_select_companies_ignores_duplicates():
    selected, _ = select_companies([ADDEPAR, ZOOX], ["Addepar", "addepar"])
    assert selected == [ADDEPAR]


def test_select_companies_reports_repeated_unknown_name_once():
    _, errors = select_companies([ADDEPAR], ["Nope", "nope"])
    assert len(errors) == 1


def test_select_companies_ignores_surrounding_spaces():
    assert select_companies([ADDEPAR, ZOOX], ["  zoox "]) == ([ZOOX], [])


def test_select_companies_empty_list_selects_nothing():
    assert select_companies([ADDEPAR, ZOOX], []) == ([], [])