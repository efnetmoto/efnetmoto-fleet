"""Dataclasses shared across the searchbot package.

Pure data containers — no I/O, no eggdrop imports.
"""

from dataclasses import dataclass


@dataclass
class SearchResult:
    """A single Brave web search result as shown to IRC."""

    title: str
    url: str


@dataclass
class CacheEntry:
    """A cached search response, keyed by the normalized query.

    ``short_urls`` holds the final display URL per result — the short URL on
    success, or the original ``SearchResult.url`` when the shortener failed.
    Fallback is resolved by the caller before caching, so this field never
    contains ``None``.

    Timestamps use ``time.monotonic()`` so expiry is immune to wall-clock
    changes; they are internal state and not meant for display.

    ``created_at`` is the cache creation time (required cached metadata) and
    doubles as the eviction-order key for the cache's entry-count cap (oldest
    first).
    """

    query: str
    results: list[SearchResult]
    short_urls: list[str]
    created_at: float
    expires_at: float
