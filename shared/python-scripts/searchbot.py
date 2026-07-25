import os
import sys
import time
import traceback

# pysource loads this file from a path outside the bot's working directory, so
# the searchbot/ package directory is not automatically on sys.path. Insert
# the shared scripts dir explicitly so `import searchbot` resolves regardless
# of the bot's cwd.
sys.path.insert(0, os.path.join(os.getcwd(), "scripts-python-shared"))

from eggdrop import bind
from eggdrop.tcl import putdcc, putlog, putserv

from searchbot import brave, cache, formatter, ratelimit, shortener
from searchbot.exceptions import BraveError, ShortenerError
from searchbot.models import CacheEntry, SearchResult


def _require_env(name: str) -> str:
    """Return a required env var or fail loudly at load time.

    Failing at load surfaces a misconfiguration in eggdrop's log immediately,
    rather than silently on the first user query.
    """
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} environment variable is not set. "
            "Set it in the bot's .env file or Ansible host_vars."
        )
    return value


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be a number, got {raw!r}")


# --- Configuration (read once at load) ---
_BRAVE_API_KEY = _require_env("BRAVE_API_KEY")
_SHORTENER_API_URL = _require_env("SHORTENER_API_URL")
_SHORTENER_API_KEY = _require_env("SHORTENER_API_KEY")
_SEARCH_TRIGGER = os.environ.get("SEARCH_TRIGGER", "!g")
_RESULT_COUNT = _env_int("RESULT_COUNT", 2)
_SEARCH_TIMEOUT = _env_float("SEARCH_TIMEOUT_SECONDS", 5.0)
_CACHE_TTL = _env_float("CACHE_TTL_SECONDS", 3600.0)
_CACHE_MAX_ENTRIES = _env_int("CACHE_MAX_ENTRIES", 1024)
_PER_USER_COOLDOWN = _env_float("PER_USER_COOLDOWN_SECONDS", 5.0)
_CHANNEL_COOLDOWN = _env_float("CHANNEL_COOLDOWN_SECONDS", 1.0)
_MAX_QUERY_LENGTH = _env_int("MAX_QUERY_LENGTH", 256)

_cache = cache.SearchCache(_CACHE_TTL, _CACHE_MAX_ENTRIES)
_rate_limiter = ratelimit.RateLimiter(_PER_USER_COOLDOWN, _CHANNEL_COOLDOWN)


def _send_results(
    results: list[SearchResult],
    short_urls: list[str],
    query: str,
    reply_target: str,
    prefix: str,
) -> None:
    """Send formatted result lines, or the no-results message, to ``reply_target``.

    Result lines carry no nick prefix (result lines are bare lines like
    "[<domain>] <bold>title</bold> → <url>"); only the no-results message is
    prefixed, since it directly addresses the asking user.
    """
    if not results:
        putserv(f"PRIVMSG {reply_target} :{prefix}No results found for: {query}")
        return
    for line in formatter.format_results(results, short_urls):
        putserv(f"PRIVMSG {reply_target} :{line}")


def _shorten_with_fallback(result: SearchResult) -> str:
    """Shorten a result's URL, falling back to the original on failure.

    Shortener failures are logged but never surface to IRC — a shortener
    outage must not block a search result, so the original URL is used as a
    fallback. Each result is shortened independently so one failure cannot
    affect another's success.
    """
    try:
        return shortener.shorten(
            result.url, _SHORTENER_API_URL, _SHORTENER_API_KEY, timeout=_SEARCH_TIMEOUT
        )
    except ShortenerError as e:
        putlog(f"searchbot: shortener error for {result.url}: {e}")
        return result.url


def _handle_search_impl(nick: str, text: str, reply_target: str, prefix: str) -> None:
    try:
        query = text.strip()
        if not query:
            putserv(
                f"PRIVMSG {reply_target} :{prefix}Usage: {_SEARCH_TRIGGER} <search query>"
                f"  (docs: https://efnetmoto.com/docs/user/search/)"
            )
            return
        if len(query) > _MAX_QUERY_LENGTH:
            putserv(
                f"PRIVMSG {reply_target} :{prefix}Query too long (max {_MAX_QUERY_LENGTH} chars)."
            )
            return

        # Cache is checked before the rate limiter: a cache hit makes no
        # upstream call, so it must not consume a rate-limit slot. The request
        # flow checks the cache before querying Brave, and rate limiting exists
        # to protect the upstreams (Brave + the shortener), not to cap IRC
        # message volume. The practical effect is that a popular repeat query
        # stays free to answer even during a per-user cooldown.
        cached = _cache.get(query)
        if cached is not None:
            _send_results(cached.results, cached.short_urls, query, reply_target, prefix)
            return

        # Rate-limit on `nick`, not `handle`: unregistered users have handle
        # "*" and would otherwise share a single bucket. A nick-change evades
        # the per-user cooldown, but the channel cooldown still holds, which
        # is an acceptable tradeoff for a single-channel bot.
        decision = _rate_limiter.check_and_record(nick)
        if not decision.allowed:
            putserv(f"PRIVMSG {reply_target} :{prefix}Rate limited — try again shortly.")
            return

        try:
            results = brave.search(
                query, _BRAVE_API_KEY, count=_RESULT_COUNT, timeout=_SEARCH_TIMEOUT
            )
        except BraveError as e:
            putlog(f"searchbot: brave error for {query!r}: {e}")
            putserv(f"PRIVMSG {reply_target} :{prefix}{e}")
            return

        # Resolve shortener fallbacks per result before caching, so a cache hit
        # serves final display URLs and never re-shortens. The shortener is
        # non-idempotent — re-shortening the same destination mints a new short
        # URL each time, so serving cached results would leak duplicates if we
        # cached the original URL and re-shortened on every cache hit.
        short_urls = [_shorten_with_fallback(r) for r in results]

        now = time.monotonic()
        _cache.set(
            query,
            CacheEntry(
                query=query,
                results=results,
                short_urls=short_urls,
                created_at=now,
                expires_at=now + _CACHE_TTL,
            ),
        )

        _send_results(results, short_urls, query, reply_target, prefix)

    except Exception:
        putlog(f"searchbot: unhandled exception in handle_search:\n{traceback.format_exc()}")
        putserv(
            f"PRIVMSG {reply_target} :{prefix}An unexpected error occurred. Please try again later."
        )


def handle_search(nick: str, host: str, handle: str, channel: str, text: str) -> None:
    """Eggdrop pub bind for the search trigger."""
    _handle_search_impl(nick, text, reply_target=channel, prefix=f"{nick}: ")


def handle_cache_bust(handle: str, idx: int, text: str) -> None:
    """Eggdrop DCC bind (flag ``m``) for the partyline cache-bust command."""
    try:
        _cache.clear()
        putdcc(idx, "searchbot: cache cleared.")
        putlog(f"searchbot: cache cleared by {handle}")
    except Exception:
        putlog(f"searchbot: unhandled exception in handle_cache_bust:\n{traceback.format_exc()}")
        putdcc(idx, "searchbot: error clearing cache.")


# Rehash safety: unbind previous iteration's binds before re-registering.
if "SEARCHBOT_BINDS" in globals():
    for b in SEARCHBOT_BINDS:
        b.unbind()
    del SEARCHBOT_BINDS

SEARCHBOT_BINDS = [
    bind("pub", "*", _SEARCH_TRIGGER, handle_search),
    bind("dcc", "m", "searchcache", handle_cache_bust),
]
