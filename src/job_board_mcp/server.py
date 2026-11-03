"""MCP server: search official job board APIs and read job descriptions."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from job_board_mcp.cache import TTLCache
from job_board_mcp.config import Company, load_companies
from job_board_mcp.fetch import CACHE_TTL_SECONDS, Fetcher, FetchError, detail_url, list_url, make_client
from job_board_mcp.lanes import load_lanes
from job_board_mcp.normalize import (
    description_ashby,
    description_greenhouse,
    description_lever,
    normalize_ashby,
    normalize_greenhouse,
    normalize_lever,
)
from job_board_mcp.search import (
    MAX_LIMIT,
    SearchFilters,
    build_search_response,
    check_lane,
    select_companies,
)

# Built from this file's location: Claude Desktop starts the server from a folder it chooses.
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
logger = logging.getLogger(__name__)

DESCRIBERS = {"greenhouse": description_greenhouse, "lever": description_lever, "ashby": description_ashby}


@dataclass
class AppState:
    fetcher: Fetcher
    companies: list[Company]
    lanes: dict


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[AppState]:
    companies = load_companies(CONFIG_DIR / "companies.yaml")
    lanes = load_lanes(CONFIG_DIR / "lanes.yaml")
    async with make_client() as client:
        yield AppState(Fetcher(client, TTLCache(CACHE_TTL_SECONDS)), companies, lanes)


mcp = MCPServer("job-board", lifespan=lifespan)


@mcp.tool()
async def list_companies(ctx: Context) -> list[dict]:
    """List the companies this server searches and which applicant tracking system each uses.

    Use these exact names in search_jobs's `companies` filter and in get_job.
    """
    state: AppState = ctx.request_context.lifespan_context
    return [{"name": company.name, "ats": company.ats} for company in state.companies]


@mcp.tool()
async def search_jobs(
    ctx: Context,
    lane: Annotated[
        str | None,
        Field(
            description=(
                "Career lane, matched against job titles: "
                "'deployment' (forward deployed, solutions, implementation, and customer engineering roles), "
                "'pm' (product and technical program management), "
                "'new_grad' (new grad, early career, and graduate programs). "
                "Senior, staff, principal, director, lead, and intern titles are never in any lane. "
                "Omit to search every title."
            )
        ),
    ] = None,
    keywords: Annotated[
        list[str] | None,
        Field(
            description=(
                "Words to find in job titles; a job matches if ANY keyword appears as whole words, in order "
                "(\"product manager\" matches \"Senior Product Manager\" but not \"Product Marketing Manager\"). "
                "Ignores lane exclusions, so senior roles can match."
            )
        ),
    ] = None,
    locations: Annotated[
        list[str] | None,
        Field(
            description=(
                "Places to find in the job's location text; a job matches if ANY entry appears. "
                "Boards write places differently, so pass synonyms together, e.g. [\"new york\", \"nyc\"] "
                "or [\"san francisco\", \"sf\", \"bay area\"]. Use `remote` for remote work, not \"remote\" here."
            )
        ),
    ] = None,
    remote: Annotated[
        bool | None,
        Field(
            description=(
                "true: only jobs the board marks as remote. false: only jobs it marks as onsite or hybrid. "
                "Uses the board's structured workplace field, not the location text. Many jobs don't say "
                "either way and are left out by both true and false, so omit this unless remote matters."
            )
        ),
    ] = None,
    companies: Annotated[
        list[str] | None,
        Field(
            description="Company names to search, from list_companies (case doesn't matter). Omit to search all."
        ),
    ] = None,
    posted_within_days: Annotated[
        int | None,
        Field(ge=0, description="Only jobs first posted within this many days, e.g. 7 for the last week."),
    ] = None,
    limit: Annotated[
        int,
        Field(
            ge=0,
            le=MAX_LIMIT,
            description="Max jobs to return, newest first. total_matches still counts every match.",
        ),
    ] = 25,
) -> dict:
    """Search open jobs across the configured companies' job boards, newest first.

    All filters are optional and combine (a job must pass every filter given).
    Returns `jobs`, `total_matches` (before `limit`), `errors` (companies that couldn't be
    searched, or unknown company names), and `warnings` (individual postings skipped
    because of bad data). To read a job's full description, pass its `company` and
    `job_id` to get_job.
    """
    state: AppState = ctx.request_context.lifespan_context

    # Only ToolError text reaches Claude; a plain ValueError shows up as a generic crash.
    try:
        check_lane(lane, state.lanes)
        filters = SearchFilters(
            lane=lane,
            keywords=keywords,
            locations=locations,
            remote=remote,
            posted_within_days=posted_within_days,
            limit=limit,
        )
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    selected, unknown = select_companies(state.companies, companies)
    results = await state.fetcher.fetch_boards(selected)
    response = build_search_response(selected, results, state.lanes, filters, datetime.now(timezone.utc))
    response["errors"] = unknown + response["errors"]

    for warning in response["warnings"]:
        logger.warning(warning)
    return response


@mcp.tool()
async def get_job(
    ctx: Context,
    company: Annotated[str, Field(description="The `company` field from a search_jobs result.")],
    job_id: Annotated[str, Field(description="The `job_id` field from the same search_jobs result.")],
) -> dict:
    """Get one job's full description as plain text, plus its title, location, URL, and posted date.

    Pass `company` and `job_id` exactly as they appear in a search_jobs result.
    """
    state: AppState = ctx.request_context.lifespan_context

    selected, unknown = select_companies(state.companies, [company])
    if unknown:
        raise ToolError(unknown[0])
    found = selected[0]

    try:
        raw = await _fetch_raw_job(state.fetcher, found, job_id)
    except FetchError as exc:
        raise ToolError(
            f"Couldn't load job {job_id} from {found.name}: {exc}. A 404 usually means the posting "
            "has closed or the job_id is wrong; run search_jobs again for current jobs."
        ) from exc

    if raw is None:
        raise ToolError(
            f"Job {job_id} isn't on {found.name}'s board anymore; the posting has probably closed. "
            "Run search_jobs again for current jobs."
        )

    # Wrap the one posting the way its list response would, so the list normalizers map
    # title, location, and date. A second mapping for detail responses would drift.
    try:
        if found.ats == "lever":
            jobs, warnings = normalize_lever([raw], found.name)
        elif found.ats == "greenhouse":
            jobs, warnings = normalize_greenhouse({"jobs": [raw]}, found.name)
        else:
            jobs, warnings = normalize_ashby({"jobs": [raw]}, found.name)
        description = DESCRIBERS[found.ats](raw)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ToolError(f"{found.name} returned job {job_id} in an unexpected format.") from exc

    if not jobs:
        # Skipped for bad data, or an unlisted Ashby posting (skipped without a warning).
        reason = warnings[0] if warnings else "the posting is unlisted"
        raise ToolError(f"Job {job_id} at {found.name} can't be shown: {reason}.")

    job = jobs[0]
    return {
        "company": job.company,
        "title": job.title,
        "location": job.location,
        "url": job.url,
        "posted_at": job.posted_at.date().isoformat(),
        "description": description,
    }


async def _fetch_raw_job(fetcher: Fetcher, company: Company, job_id: str) -> dict | None:
    """Return the raw posting, or None if Ashby's list doesn't have it. Raises FetchError."""
    if company.ats != "ashby":
        return await fetcher.fetch_json(detail_url(company, job_id))

    # Ashby has no public detail endpoint; the (cached) list includes full descriptions.
    board = await fetcher.fetch_json(list_url(company))
    postings = board.get("jobs") if isinstance(board, dict) else None
    for posting in postings or []:
        if isinstance(posting, dict) and str(posting.get("id")) == job_id:
            return posting
    return None


def main() -> None:
    # logging writes to stderr. Never print(): with stdio, stdout carries the MCP messages.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # httpx logs every request at INFO (~22 per search), which would bury the posting warnings.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    mcp.run()
