"""In-memory TTL cache for search responses, keyed by normalized query."""

import time

from searchbot.models import CacheEntry


def _normalize(query: str) -> str:
    """Fold a query to its cache key: whitespace-collapsed and lowercased.

    ``split()`` + ``" ".join`` strips leading/trailing whitespace AND collapses
    internal runs (including tabs/newlines) to a single space, so "Rust  Async",
    "Rust Async", and "  rust async  " all collide. The cache key is the query
    text rather than exact bytes; case is folded so capitalization differences
    also hit. Collapsing internal whitespace is strictly more robust than
    ``strip`` alone and has no downside for lookups.
    """
    return " ".join(query.split()).lower()


class SearchCache:
    """A dict-backed TTL cache with an optional entry-count cap.

    Synchronous-only: eggdrop pub binds run on the main thread, so no locking
    is needed around the internal dict. State is lost on script reload, which
    matches the fleet's rehash-safety pattern.

    Bounding: TTL is enforced lazily on read; an optional ``max_entries`` cap
    prevents unbounded growth under a flood of unique queries by evicting the
    oldest entry (smallest ``created_at``) when the cap is exceeded. Without a
    cap the store grows monotonically until rehash — acceptable for a single
    channel, but not under sustained abuse of the search command.
    """

    def __init__(self, ttl_seconds: float, max_entries: int | None = None) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._store: dict[str, CacheEntry] = {}

    def get(self, query: str) -> CacheEntry | None:
        """Return a live cache entry for ``query``, or None on miss/expiry."""
        key = _normalize(query)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() >= entry.expires_at:
            # Lazy eviction of the single expired entry on read.
            del self._store[key]
            return None
        return entry

    def set(self, query: str, entry: CacheEntry) -> None:
        """Store ``entry`` under the normalized form of ``query``.

        When a ``max_entries`` cap is set and a *new* key pushes the store past
        it, the oldest entry (smallest ``created_at``) is evicted. Overwriting
        an existing key never triggers eviction — it replaces in place, which
        also resets its eviction priority to "newest" (the new ``created_at``).

        The eviction scan is O(n) in the store size, which is acceptable at
        the default ``max_entries=1024``; a query flood large enough to make
        this hot is caught by the rate limiter before the cache grows much.
        """
        key = _normalize(query)
        is_new = key not in self._store
        self._store[key] = entry
        if self._max_entries is not None and is_new and len(self._store) > self._max_entries:
            oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
            del self._store[oldest_key]

    def clear(self) -> None:
        """Drop every cache entry (partyline cache-bust command)."""
        self._store.clear()

    def __contains__(self, query: str) -> bool:
        """True iff a *live* (unexpired) entry exists for ``query``.

        Liveness-aware so ``x in cache`` implies ``cache.get(x) is not None``.
        Does not evict (no side effect); use ``get`` for lazy eviction.
        Provided so tests and callers need not reach into the private ``_store``.
        """
        entry = self._store.get(_normalize(query))
        if entry is None:
            return False
        return time.monotonic() < entry.expires_at

    def __len__(self) -> int:
        """Number of entries held (live or expired-but-not-yet-evicted)."""
        return len(self._store)
