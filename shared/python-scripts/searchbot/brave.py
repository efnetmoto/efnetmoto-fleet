"""Brave Search API client.

One function, no retries, user-safe errors via ``BraveError``. The API key is
sent only via the ``X-Subscription-Token`` header and is never included in
exception messages.
"""

import re
from urllib.parse import urlparse

import requests

from searchbot.exceptions import BraveError
from searchbot.models import SearchResult

_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
# Every upstream failure surfaces the same user-safe string. Centralizing it
# makes the "BraveError messages are user-safe" contract structural rather
# than a convention to keep in sync across seven raise sites.
_UNAVAILABLE = "Search temporarily unavailable."
_HEADERS = {
    "Accept": "application/json",
    # Accept-Encoding is intentionally omitted: requests/urllib3 negotiate
    # gzip+deflate automatically.
}


def _domain_of(url: str) -> str:
    """Return a display domain for ``url``, stripping a leading ``www.``.

    Brave URLs are expected to be absolute with a scheme, so ``urlparse``
    yields a real hostname. For anything malformed we degrade to ``netloc``
    then to the raw ``url`` rather than raising — a single weird result must
    not sink the whole response (the shortener-fallback philosophy: never
    let one failure block a result).
    """
    parsed = urlparse(url)
    host = parsed.hostname or parsed.netloc
    if not host:
        return url
    return host[4:] if host.startswith("www.") else host


# IRC delimits messages with CRLF, so a newline embedded in a Brave result
# title would terminate Pompone's PRIVMSG and the remainder would be parsed
# as a fresh IRC command issued by the bot — command injection from any page
# Brave indexes. Sanitize at ingestion so the invariant lives on the model
# and every display site (putserv, future ones) inherits it.
#
# Line/whitespace control chars (\r \n \t \f \v) become a space so words
# stay separated; the rest of the C0 range and DEL (mIRC formatting codes
# like bold/color, plus other nonprintables) are dropped — they would break
# the formatter's own \x02 pairing or render as garbage. Runs of spaces
# collapse, and the title is capped to keep the full IRC line under the
# 512-byte limit for typical (mostly-ASCII) titles.
_NEWLINE_TO_SPACE = re.compile(r"[\r\n\t\f\v]")
_OTHER_CONTROL = re.compile(r"[\x00-\x08\x0e-\x1f\x7f]")
_MULTISPACE = re.compile(r" {2,}")
_MAX_TITLE_LEN = 150


def _sanitize_title(title: str) -> str:
    """Return an IRC-safe, length-capped view of a Brave result title."""
    cleaned = _OTHER_CONTROL.sub("", _NEWLINE_TO_SPACE.sub(" ", title))
    cleaned = _MULTISPACE.sub(" ", cleaned).strip()
    if len(cleaned) <= _MAX_TITLE_LEN:
        return cleaned
    return cleaned[: _MAX_TITLE_LEN - 1].rstrip() + "…"


def search(query: str, api_key: str, count: int = 2, timeout: float = 5.0) -> list[SearchResult]:
    """Query Brave web search and return up to ``count`` results.

    Args:
        query: The user's search query (already stripped/validated by caller).
        api_key: Brave API key (sent via ``X-Subscription-Token``).
        count: Maximum results to request and return.
        timeout: Per-request timeout in seconds.

    Returns:
        Zero or more ``SearchResult`` objects (title + url), up to ``count``.

    Raises:
        BraveError: On timeout, connection failure, non-200, malformed JSON,
            or a result missing ``title``/``url``. The message is user-safe.
    """
    headers = {**_HEADERS, "X-Subscription-Token": api_key}
    params = {"q": query, "count": count}

    try:
        resp = requests.get(_BRAVE_ENDPOINT, headers=headers, params=params, timeout=timeout)
    except requests.Timeout:
        raise BraveError("Search timed out.")
    except requests.ConnectionError:
        raise BraveError(_UNAVAILABLE)

    if resp.status_code != 200:
        raise BraveError(_UNAVAILABLE)

    try:
        data = resp.json()
    except ValueError:  # requests.JSONDecodeError subclasses ValueError
        raise BraveError(_UNAVAILABLE)
    if not isinstance(data, dict):
        raise BraveError(_UNAVAILABLE)

    # Missing `web`/`results` keys are treated as zero results, not an error;
    # a non-list `results` is genuinely malformed.
    web = data.get("web")
    if not isinstance(web, dict):
        raw_results: list = []
    else:
        raw_results = web.get("results", [])
    if not isinstance(raw_results, list):
        raise BraveError(_UNAVAILABLE)

    results: list[SearchResult] = []
    for raw in raw_results[:count]:
        if not isinstance(raw, dict):
            raise BraveError(_UNAVAILABLE)
        # `raw` is proven a dict by the guard above, so subscript can only
        # raise KeyError here — TypeError would require a non-dict mapping.
        try:
            title = raw["title"]
            url = raw["url"]
        except KeyError:
            raise BraveError(_UNAVAILABLE)
        # Brave occasionally returns non-string fields (e.g. a null title).
        # Passing a non-string to _sanitize_title or urlparse raises TypeError,
        # which would bypass BraveError and surface as an "unexpected error" to
        # IRC. Validate here so all malformed-result paths stay within the
        # user-safe BraveError contract.
        if not isinstance(title, str) or not isinstance(url, str):
            raise BraveError(_UNAVAILABLE)
        results.append(SearchResult(title=_sanitize_title(title), url=url, domain=_domain_of(url)))
    return results
