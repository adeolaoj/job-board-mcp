import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from job_board_mcp.cache import TTLCache
from job_board_mcp.config import Company
from job_board_mcp.fetch import Fetcher, detail_url, list_url
from job_board_mcp.lanes import load_lanes
from job_board_mcp.server import CONFIG_DIR, AppState, get_job, list_companies, search_jobs

FIXTURES = Path(__file__).parent / "fixtures"

ADDEPAR = Company(name="Addepar", ats="greenhouse", slug="addepar1")
ZOOX = Company(name="Zoox", ats="lever", slug="zoox")
DEEPGRAM = Company(name="Deepgram", ats="ashby", slug="deepgram")

GREENHOUSE_JOB_ID = "8756273002"
LEVER_JOB_ID = "0a22d356-f7f7-4374-b393-55637772edda"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_ctx(routes):
    """A Context stand-in whose fetcher answers each URL in routes and 404s everything else."""

    def handler(request):
        if str(request.url) in routes:
            return httpx.Response(200, json=routes[str(request.url)])
        return httpx.Response(404, json={"error": "not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    state = AppState(
        Fetcher(client, TTLCache(ttl_seconds=900)),
        [ADDEPAR, ZOOX, DEEPGRAM],
        load_lanes(CONFIG_DIR / "lanes.yaml"),
    )
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=state))


@pytest.fixture
def ctx():
    return make_ctx({
        list_url(ADDEPAR): load_fixture("greenhouse_jobs.json"),
        list_url(ZOOX): load_fixture("lever_jobs.json"),
        list_url(DEEPGRAM): load_fixture("ashby_jobs.json"),
        detail_url(ADDEPAR, GREENHOUSE_JOB_ID): load_fixture("greenhouse_job_detail.json"),
        detail_url(ZOOX, LEVER_JOB_ID): load_fixture("lever_job_detail.json"),
    })


def test_config_dir_is_the_repo_config_folder():
    # Must not depend on the working directory: Claude Desktop picks its own.
    assert (CONFIG_DIR / "companies.yaml").is_file()
    assert (CONFIG_DIR / "lanes.yaml").is_file()


# --- list_companies ---

@pytest.mark.anyio
async def test_list_companies(ctx):
    assert await list_companies(ctx) == [
        {"name": "Addepar", "ats": "greenhouse"},
        {"name": "Zoox", "ats": "lever"},
        {"name": "Deepgram", "ats": "ashby"},
    ]


# --- search_jobs ---

@pytest.mark.anyio
async def test_search_jobs_returns_every_board(ctx):
    response = await search_jobs(ctx)

    assert response["total_matches"] == 14
    assert response["errors"] == []


@pytest.mark.anyio
async def test_search_jobs_unknown_lane_is_a_tool_error(ctx):
    # A plain ValueError would reach Claude as a generic crash, without the valid lanes.
    with pytest.raises(ToolError, match="deployment"):
        await search_jobs(ctx, lane="product")


@pytest.mark.anyio
async def test_search_jobs_unknown_company_goes_in_errors(ctx):
    response = await search_jobs(ctx, companies=["zoox", "Nope"])

    assert {job["company"] for job in response["jobs"]} == {"Zoox"}
    assert len(response["errors"]) == 1
    assert "Nope" in response["errors"][0]


# --- get_job ---

@pytest.mark.anyio
async def test_get_job_greenhouse(ctx):
    job = await get_job(ctx, "Addepar", GREENHOUSE_JOB_ID)

    assert job["title"] == "AddeGrad Program (2027) - Client Solutions Analyst"
    assert job["company"] == "Addepar"
    assert job["location"] == "Edinburgh, UK"
    assert job["url"] == "https://job-boards.greenhouse.io/addepar1/jobs/8756273002"
    assert job["posted_at"] == "2026-10-01"
    assert job["description"].startswith("Who We Are")


@pytest.mark.anyio
async def test_get_job_lever(ctx):
    job = await get_job(ctx, "zoox", LEVER_JOB_ID)  # company name ignores case

    assert job["title"] == "Technical Program Manager, PMO - Test Fleet Program (Contract)"
    assert job["company"] == "Zoox"
    assert job["posted_at"] == "2026-06-18"
    assert "In this Role, You Will..." in job["description"]


@pytest.mark.anyio
async def test_get_job_ashby_reads_the_list(ctx):
    posting = load_fixture("ashby_jobs.json")["jobs"][0]

    job = await get_job(ctx, "Deepgram", posting["id"])

    assert job["title"] == posting["title"]
    assert job["url"] == posting["jobUrl"]
    assert job["description"] == posting["descriptionPlain"].strip()


@pytest.mark.anyio
async def test_get_job_closed_ashby_posting(ctx):
    with pytest.raises(ToolError, match="probably closed"):
        await get_job(ctx, "Deepgram", "no-such-id")


@pytest.mark.anyio
async def test_get_job_closed_detail_posting(ctx):
    # Greenhouse and Lever answer a closed posting's detail URL with a 404.
    with pytest.raises(ToolError, match="404"):
        await get_job(ctx, "Zoox", "no-such-id")


@pytest.mark.anyio
async def test_get_job_unknown_company_lists_configured_names(ctx):
    with pytest.raises(ToolError, match="Configured companies: Addepar, Zoox, Deepgram"):
        await get_job(ctx, "Nope", "123")


@pytest.mark.anyio
async def test_get_job_unlisted_ashby_posting(ctx):
    board = load_fixture("ashby_jobs.json")
    board["jobs"][0]["isListed"] = False
    unlisted_ctx = make_ctx({list_url(DEEPGRAM): board})

    with pytest.raises(ToolError, match="unlisted"):
        await get_job(unlisted_ctx, "Deepgram", board["jobs"][0]["id"])


@pytest.mark.anyio
async def test_get_job_unexpected_format(ctx):
    bad_ctx = make_ctx({detail_url(ADDEPAR, GREENHOUSE_JOB_ID): ["not", "a", "posting"]})

    with pytest.raises(ToolError, match="unexpected format"):
        await get_job(bad_ctx, "Addepar", GREENHOUSE_JOB_ID)
