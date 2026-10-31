import httpx
import pytest

from job_board_mcp.cache import TTLCache
from job_board_mcp.config import Company
from job_board_mcp.fetch import (
    USER_AGENT,
    Fetcher,
    FetchError,
    detail_url,
    list_url,
    make_client,
)

ADDEPAR = Company(name="Addepar", ats="greenhouse", slug="addepar1")
ZOOX = Company(name="Zoox", ats="lever", slug="zoox")
DEEPGRAM = Company(name="Deepgram", ats="ashby", slug="deepgram")


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make_fetcher(handler, clock=None):
    """A Fetcher whose client never touches the network: handler plays the server."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = TTLCache(ttl_seconds=900, clock=clock or FakeClock())
    return Fetcher(client, cache)


# --- URLs (plain functions, no async needed) ---

def test_list_urls():
    assert list_url(ADDEPAR) == "https://boards-api.greenhouse.io/v1/boards/addepar1/jobs"
    assert list_url(ZOOX) == "https://api.lever.co/v0/postings/zoox?mode=json"
    assert list_url(DEEPGRAM) == "https://api.ashbyhq.com/posting-api/job-board/deepgram"


def test_detail_urls():
    assert detail_url(ADDEPAR, "8756273002") == (
        "https://boards-api.greenhouse.io/v1/boards/addepar1/jobs/8756273002"
    )
    assert detail_url(ZOOX, "0a22d356-f7f7-4374-b393-55637772edda") == (
        "https://api.lever.co/v0/postings/zoox/0a22d356-f7f7-4374-b393-55637772edda?mode=json"
    )


def test_ashby_has_no_detail_url():
    with pytest.raises(ValueError):
        detail_url(DEEPGRAM, "anything")


def test_unsupported_ats_raises_value_error():
    unsupported = Company(name="Unsupported", ats="unknown", slug="unknown")

    with pytest.raises(ValueError, match="Unsupported ATS"):
        list_url(unsupported)

    with pytest.raises(ValueError, match="Unsupported ATS"):
        detail_url(unsupported, "job-id")


def test_client_sends_user_agent():
    client = make_client()
    assert client.headers["User-Agent"] == USER_AGENT
    assert client.timeout.read == 10.0


# --- fetch_json ---

@pytest.mark.anyio
async def test_fetch_json_returns_parsed_json():
    fetcher = make_fetcher(lambda request: httpx.Response(200, json={"jobs": []}))
    assert await fetcher.fetch_json("https://example.com/jobs") == {"jobs": []}


@pytest.mark.anyio
async def test_second_fetch_uses_cache():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"jobs": []})

    fetcher = make_fetcher(handler)
    await fetcher.fetch_json("https://example.com/jobs")
    await fetcher.fetch_json("https://example.com/jobs")

    assert len(requests) == 1


@pytest.mark.anyio
async def test_cached_json_null_is_a_cache_hit():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            content=b"null",
            headers={"Content-Type": "application/json"},
        )

    fetcher = make_fetcher(handler)
    url = "https://example.com/jobs"

    assert await fetcher.fetch_json(url) is None
    assert await fetcher.fetch_json(url) is None
    assert len(requests) == 1


@pytest.mark.anyio
async def test_refetches_after_cache_expires():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"jobs": []})

    clock = FakeClock()
    fetcher = make_fetcher(handler, clock)
    await fetcher.fetch_json("https://example.com/jobs")
    clock.now = 900
    await fetcher.fetch_json("https://example.com/jobs")

    assert len(requests) == 2


@pytest.mark.anyio
async def test_failures_are_not_cached():
    responses = [httpx.Response(500), httpx.Response(200, json={"jobs": ["ok"]})]
    fetcher = make_fetcher(lambda request: responses.pop(0))

    with pytest.raises(FetchError):
        await fetcher.fetch_json("https://example.com/jobs")
    assert await fetcher.fetch_json("https://example.com/jobs") == {"jobs": ["ok"]}


@pytest.mark.anyio
async def test_plain_text_404_raises_fetch_error_with_status():
    # Ashby answers a wrong slug with a plain-text "Not Found", not JSON.
    fetcher = make_fetcher(lambda request: httpx.Response(404, text="Not Found"))

    with pytest.raises(FetchError, match="404"):
        await fetcher.fetch_json("https://api.ashbyhq.com/posting-api/job-board/wrong")


@pytest.mark.anyio
async def test_non_json_200_raises_fetch_error():
    fetcher = make_fetcher(lambda request: httpx.Response(200, text="<html>maintenance</html>"))

    with pytest.raises(FetchError):
        await fetcher.fetch_json("https://example.com/jobs")


@pytest.mark.anyio
async def test_invalid_utf8_json_raises_fetch_error():
    fetcher = make_fetcher(
        lambda request: httpx.Response(
            200,
            content=b'{"a": "\xff"}',
            headers={"Content-Type": "application/json"},
        )
    )

    with pytest.raises(FetchError, match="not valid JSON") as exc_info:
        await fetcher.fetch_json("https://example.com/jobs")

    assert isinstance(exc_info.value.__cause__, UnicodeDecodeError)


@pytest.mark.anyio
async def test_network_error_raises_fetch_error():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    fetcher = make_fetcher(handler)

    with pytest.raises(FetchError, match="ConnectError") as exc_info:
        await fetcher.fetch_json("https://example.com/jobs")

    assert isinstance(exc_info.value.__cause__, httpx.ConnectError)


# --- fetch_boards ---

@pytest.mark.anyio
async def test_fetch_boards_keeps_order_and_isolates_failures():
    def handler(request):
        if "addepar1" in str(request.url):
            return httpx.Response(200, json={"jobs": ["addepar job"]})
        if "zoox" in str(request.url):
            return httpx.Response(404, json={"ok": False, "error": "Document not found"})
        return httpx.Response(200, json={"jobs": ["deepgram job"]})

    fetcher = make_fetcher(handler)
    results = await fetcher.fetch_boards([ADDEPAR, ZOOX, DEEPGRAM])

    assert results[0] == {"jobs": ["addepar job"]}
    assert isinstance(results[1], FetchError)
    assert results[2] == {"jobs": ["deepgram job"]}