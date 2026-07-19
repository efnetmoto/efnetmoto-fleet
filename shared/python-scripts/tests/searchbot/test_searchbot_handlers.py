# Tests for handler functions in searchbot.py (the eggdrop entry point).
# eggdrop from-imports (bind, putlog, putserv, putdcc) are mocked; searchbot.py
# is loaded by file path via importlib because `import searchbot` resolves to
# the searchbot/ package.
import importlib.util
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

from searchbot.exceptions import BraveError, ShortenerError
from searchbot.models import CacheEntry, SearchResult
from searchbot.ratelimit import RateLimiter

# conftest.py installs the eggdrop mock before any test file is imported. Wire
# named mocks onto it so from-imports in searchbot.py resolve to the exact
# objects these tests assert on. These must be module-level: exec_module below
# binds searchbot.py's local names to these objects at import time, so creating
# fresh mocks per-test in fixtures would not be seen by searchbot.py.
_eggdrop_mock = sys.modules["eggdrop"]
_putserv = MagicMock()
_putlog = MagicMock()
_putdcc = MagicMock()
_bind = MagicMock(return_value=MagicMock())
_eggdrop_mock.bind = _bind
_eggdrop_mock.tcl.putserv = _putserv
_eggdrop_mock.tcl.putlog = _putlog
_eggdrop_mock.tcl.putdcc = _putdcc

# Load searchbot.py by file path — `import searchbot` would resolve to the
# searchbot/ package, not the entry-point script.
_script_path = pathlib.Path(__file__).parents[2] / "searchbot.py"
_spec = importlib.util.spec_from_file_location("searchbot_script", _script_path)
sb = importlib.util.module_from_spec(_spec)
sys.modules["searchbot_script"] = sb
_spec.loader.exec_module(sb)


@pytest.fixture
def putserv_mock():
    return _putserv


@pytest.fixture
def putlog_mock():
    return _putlog


@pytest.fixture
def putdcc_mock():
    return _putdcc


@pytest.fixture(autouse=True)
def reset_mocks(putserv_mock, putlog_mock, putdcc_mock):
    putserv_mock.reset_mock()
    putlog_mock.reset_mock()
    putdcc_mock.reset_mock()
    # Clear the in-memory cache and give each test a fresh limiter with zero
    # cooldowns, so cache-hit and multi-call tests aren't tripped by the real
    # 5s/1s cooldowns. Rate-limit tests replace this limiter themselves.
    sb._cache.clear()
    sb._rate_limiter = RateLimiter(0.0, 0.0)


def _sent_messages(putserv_mock):
    return [call[0][0] for call in putserv_mock.call_args_list]


# --- empty / validation ---


def test_empty_query_replies_usage(putserv_mock):
    sb.handle_search("alice", "h", "hand", "#moto", "")
    putserv_mock.assert_called_once()
    assert putserv_mock.call_args[0][0] == "PRIVMSG #moto :alice: Usage: !g <search query>"


def test_whitespace_only_query_replies_usage(putserv_mock):
    sb.handle_search("alice", "h", "hand", "#moto", "   ")
    putserv_mock.assert_called_once()
    assert "Usage: !g" in putserv_mock.call_args[0][0]


def test_overlong_query_rejected(putserv_mock):
    long_q = "x" * (sb._MAX_QUERY_LENGTH + 1)
    with patch.object(sb.brave, "search") as mock_search:
        sb.handle_search("alice", "h", "hand", "#moto", long_q)
    putserv_mock.assert_called_once()
    assert "too long" in putserv_mock.call_args[0][0].lower()
    # The length guard must short-circuit before any upstream call.
    mock_search.assert_not_called()


# --- rate limiting ---


def test_rate_limited_replies_cooldown_message(putserv_mock):
    sb._rate_limiter = RateLimiter(5.0, 5.0)
    with patch.object(sb.brave, "search", return_value=[]) as mock_search:
        sb.handle_search("alice", "h", "hand", "#moto", "rust")
        sb.handle_search("alice", "h", "hand", "#moto", "rust again")
    msgs = _sent_messages(putserv_mock)
    assert any("No results found" in m for m in msgs)  # first call completed
    assert any("Rate limited" in m for m in msgs)  # second call denied
    # The denied call must not reach Brave.
    assert mock_search.call_count == 1


def test_rate_limit_message_uses_nick_prefix(putserv_mock):
    sb._rate_limiter = RateLimiter(5.0, 0.0)
    with patch.object(sb.brave, "search", return_value=[]):
        # Two distinct queries so the second is a cache miss and reaches the
        # rate limiter (a repeat of the same query would be a cache hit and
        # never hit the limiter, per the cache-first ordering).
        sb.handle_search("alice", "h", "hand", "#moto", "rust")
        sb.handle_search("alice", "h", "hand", "#moto", "rust again")
    rate_msgs = [m for m in _sent_messages(putserv_mock) if "Rate limited" in m]
    assert rate_msgs
    assert rate_msgs[0].startswith("PRIVMSG #moto :alice: ")


# --- cache ---


def test_cache_hit_skips_brave_and_shortener(putserv_mock):
    entry = CacheEntry(
        query="rust async",
        results=[
            SearchResult("Rust Programming Language", "https://www.rust-lang.org/"),
            SearchResult("The Rust Book", "https://doc.rust-lang.org/book/"),
        ],
        short_urls=["https://go.efnetmoto.com/a7K2", "https://go.efnetmoto.com/b91Q"],
        created_at=0.0,
        expires_at=1e12,
    )
    with (
        patch.object(sb._cache, "get", return_value=entry),
        patch.object(sb.brave, "search") as mock_search,
        patch.object(sb.shortener, "shorten") as mock_shorten,
    ):
        sb.handle_search("alice", "h", "hand", "#moto", "rust async")
    mock_search.assert_not_called()
    mock_shorten.assert_not_called()
    msgs = _sent_messages(putserv_mock)
    assert "PRIVMSG #moto :1. Rust Programming Language — https://go.efnetmoto.com/a7K2" in msgs
    assert "PRIVMSG #moto :2. The Rust Book — https://go.efnetmoto.com/b91Q" in msgs


def test_successful_search_populates_cache(putserv_mock):
    results = [SearchResult("T", "https://x")]
    with (
        patch.object(sb.brave, "search", return_value=results),
        patch.object(sb.shortener, "shorten", return_value="https://s"),
    ):
        sb.handle_search("alice", "h", "hand", "#moto", "rust")
    assert sb._cache.get("rust") is not None


def test_zero_results_cached_skips_brave_on_repeat(putserv_mock):
    with patch.object(sb.brave, "search", return_value=[]) as mock_search:
        sb.handle_search("alice", "h", "hand", "#moto", "nonsense")
        sb.handle_search("bob", "h", "hand", "#moto", "nonsense")
    assert mock_search.call_count == 1
    msgs = _sent_messages(putserv_mock)
    assert all("No results found" in m for m in msgs)


def test_repeat_query_normalized_hits_cache_skips_brave(putserv_mock):
    """A repeat query differing only in case/whitespace is a cache hit.

    Also confirms the cache-first ordering: the second call must not reach the
    rate limiter or Brave even though it is the same logical query as the first.
    """
    with (
        patch.object(
            sb.brave, "search", return_value=[SearchResult("T", "https://x")]
        ) as mock_search,
        patch.object(sb.shortener, "shorten", return_value="https://s"),
    ):
        sb.handle_search("alice", "h", "hand", "#moto", "Rust Async")
        sb.handle_search("bob", "h", "hand", "#moto", "  rust   async  ")
    assert mock_search.call_count == 1


# --- Brave errors ---


def test_brave_error_replies_with_message(putserv_mock, putlog_mock):
    with patch.object(sb.brave, "search", side_effect=BraveError("Search timed out.")):
        sb.handle_search("alice", "h", "hand", "#moto", "rust")
    putserv_mock.assert_called_once()
    assert putserv_mock.call_args[0][0] == "PRIVMSG #moto :alice: Search timed out."
    putlog_mock.assert_called()


def test_zero_results_replies_no_results(putserv_mock):
    with patch.object(sb.brave, "search", return_value=[]):
        sb.handle_search("alice", "h", "hand", "#moto", "nonsense")
    putserv_mock.assert_called_once()
    assert putserv_mock.call_args[0][0] == "PRIVMSG #moto :alice: No results found for: nonsense"


# --- shortener fallback ---


def test_shortener_failure_falls_back_to_original_url(putserv_mock, putlog_mock):
    results = [
        SearchResult("First", "https://first.example/long"),
        SearchResult("Second", "https://second.example/long"),
    ]

    def shorten_side(url, api_url, api_key, timeout=5.0):
        if url == "https://first.example/long":
            raise ShortenerError("shortener returned HTTP 500")
        return "https://go.efnetmoto.com/xyz"

    with (
        patch.object(sb.brave, "search", return_value=results),
        patch.object(sb.shortener, "shorten", side_effect=shorten_side),
    ):
        sb.handle_search("alice", "h", "hand", "#moto", "test")
    msgs = _sent_messages(putserv_mock)
    assert msgs[0] == "PRIVMSG #moto :1. First — https://first.example/long"
    assert msgs[1] == "PRIVMSG #moto :2. Second — https://go.efnetmoto.com/xyz"
    # The failure was logged (with the destination URL, never the API key).
    assert any("shortener error" in c[0][0] for c in putlog_mock.call_args_list)
    assert not any("super-secret" in c[0][0] for c in putlog_mock.call_args_list)


# --- full happy path ---


def test_full_happy_path(putserv_mock):
    results = [
        SearchResult("Rust Programming Language", "https://www.rust-lang.org/"),
        SearchResult("The Rust Book", "https://doc.rust-lang.org/book/"),
    ]
    short_urls = ["https://go.efnetmoto.com/a7K2", "https://go.efnetmoto.com/b91Q"]
    with (
        patch.object(sb.brave, "search", return_value=results),
        patch.object(sb.shortener, "shorten", side_effect=short_urls),
    ):
        sb.handle_search("alice", "h", "hand", "#moto", "rust async")
    msgs = _sent_messages(putserv_mock)
    assert len(msgs) == 2
    assert msgs[0] == "PRIVMSG #moto :1. Rust Programming Language — https://go.efnetmoto.com/a7K2"
    assert msgs[1] == "PRIVMSG #moto :2. The Rust Book — https://go.efnetmoto.com/b91Q"


# --- catch-all ---


def test_unexpected_exception_replies_generic(putserv_mock, putlog_mock):
    with patch.object(sb.brave, "search", side_effect=RuntimeError("boom")):
        sb.handle_search("alice", "h", "hand", "#moto", "rust")
    putserv_mock.assert_called_once()
    assert "unexpected error" in putserv_mock.call_args[0][0].lower()
    putlog_mock.assert_called()


# --- partyline cache bust ---


def test_cache_bust_clears_and_confirms(putdcc_mock, putlog_mock):
    sb._cache.set("foo", CacheEntry("foo", [], [], 0.0, 1e12))
    assert sb._cache.get("foo") is not None
    sb.handle_cache_bust("tedski", 7, "")
    assert sb._cache.get("foo") is None
    putdcc_mock.assert_called_once()
    assert putdcc_mock.call_args[0][0] == 7
    assert "cache cleared" in putdcc_mock.call_args[0][1]
    assert any(
        "cache cleared by" in c[0][0] and "tedski" in c[0][0] for c in putlog_mock.call_args_list
    )


def test_cache_bust_exception_logged_not_raised(putdcc_mock, putlog_mock):
    with patch.object(sb._cache, "clear", side_effect=RuntimeError("boom")):
        sb.handle_cache_bust("tedski", 7, "")
    assert any("error clearing cache" in c[0][1] for c in putdcc_mock.call_args_list)
    assert putlog_mock.called


# --- bind registration ---


@pytest.mark.parametrize(
    "kind,flags,command,handler_name",
    [
        ("pub", "*", "!g", "handle_search"),
        ("dcc", "m", "searchcache", "handle_cache_bust"),
    ],
)
def test_bind_registered(kind, flags, command, handler_name):
    """Each (kind, flags, command) is bound to the named handler exactly."""
    expected = (kind, flags, command, getattr(sb, handler_name))
    assert expected in [call[0] for call in _bind.call_args_list]
