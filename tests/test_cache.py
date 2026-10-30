from job_board_mcp.cache import TTLCache


class FakeClock:
    """A clock the test controls. Calling it returns the current fake time in seconds."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_missing_key_returns_none():
    cache = TTLCache(ttl_seconds=900, clock=FakeClock())
    assert cache.get("https://example.com") is None


def test_returns_value_before_expiry():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=900, clock=clock)
    cache.set("https://example.com", {"jobs": []})

    clock.now = 899
    assert cache.get("https://example.com") == {"jobs": []}


def test_expires_at_ttl():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=900, clock=clock)
    cache.set("https://example.com", {"jobs": []})

    clock.now = 900
    assert cache.get("https://example.com") is None


def test_set_again_resets_the_timer():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=900, clock=clock)
    cache.set("https://example.com", "old")

    clock.now = 600
    cache.set("https://example.com", "new")

    clock.now = 1200  # 600s after the second set, so still fresh
    assert cache.get("https://example.com") == "new"