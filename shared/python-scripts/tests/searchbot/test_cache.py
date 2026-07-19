import time

from searchbot.cache import SearchCache
from searchbot.models import CacheEntry, SearchResult


def _make_entry(query: str = "test", ttl: float = 3600.0) -> CacheEntry:
    now = time.monotonic()
    return CacheEntry(
        query=query,
        results=[],
        short_urls=[],
        created_at=now,
        expires_at=now + ttl,
    )


def test_normalize_via_set_get():
    """Whitespace (incl. internal runs) and case all fold to the same key."""
    c = SearchCache(ttl_seconds=3600)
    entry = _make_entry()
    c.set("Rust Async Programming", entry)
    assert c.get("  rust async programming  ") is entry
    assert c.get("RUST ASYNC PROGRAMMING") is entry
    assert c.get("Rust  Async\tProgramming") is entry  # internal whitespace collapses


def test_get_miss_returns_none():
    c = SearchCache(ttl_seconds=3600)
    assert c.get("never set") is None


def test_live_entry_returned():
    c = SearchCache(ttl_seconds=3600)
    entry = _make_entry(ttl=100.0)
    c.set("test", entry)
    assert c.get("test") is entry


def test_expired_entry_returns_none_and_evicts():
    c = SearchCache(ttl_seconds=3600)
    c.set("test", _make_entry(ttl=-1.0))  # already expired
    assert c.get("test") is None
    # Lazy eviction: the expired entry is gone from the store.
    assert "test" not in c


def test_clear_removes_all():
    c = SearchCache(ttl_seconds=3600)
    c.set("a", _make_entry("a"))
    c.set("b", _make_entry("b"))
    c.clear()
    assert c.get("a") is None
    assert c.get("b") is None


def test_stored_results_round_trip():
    c = SearchCache(ttl_seconds=3600)
    results = [SearchResult("T", "https://x", "x")]
    entry = CacheEntry(
        query="q",
        results=results,
        short_urls=["https://s"],
        created_at=time.monotonic(),
        expires_at=time.monotonic() + 3600.0,
    )
    c.set("q", entry)
    got = c.get("q")
    assert got is not None
    assert got.results == results
    assert got.short_urls == ["https://s"]


def test_max_entries_evicts_oldest():
    """When the cap is exceeded, the oldest entry (smallest created_at) is evicted."""
    c = SearchCache(ttl_seconds=3600, max_entries=2)
    c.set("a", CacheEntry("a", [], [], 0.0, 1e12))
    c.set("b", CacheEntry("b", [], [], 10.0, 1e12))
    c.set("c", CacheEntry("c", [], [], 20.0, 1e12))
    # "a" has the smallest created_at and is evicted; "b" and "c" remain.
    assert c.get("a") is None
    assert c.get("b") is not None
    assert c.get("c") is not None
    assert len(c) == 2


def test_overwrite_existing_key_does_not_trigger_eviction():
    """Updating an existing key replaces in place — never evicts, even at the cap."""
    c = SearchCache(ttl_seconds=3600, max_entries=1)
    c.set("a", CacheEntry("a", [], [], 0.0, 1e12))
    c.set("a", CacheEntry("a", [], [], 5.0, 1e12))  # overwrite, not a new key
    assert len(c) == 1
    assert c.get("a") is not None


def test_no_cap_grows_unbounded():
    """Without a cap, the store holds every entry (the default path)."""
    c = SearchCache(ttl_seconds=3600)
    for i in range(5):
        c.set(f"k{i}", CacheEntry(f"k{i}", [], [], float(i), 1e12))
    assert len(c) == 5
