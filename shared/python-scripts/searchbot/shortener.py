"""URL Shortener API client.

One function, no retries (retry policy is the caller's). On any non-201 path
this raises ``ShortenerError``; the caller logs and falls back to the original
URL. The API key is sent only via the ``Authorization`` header and never
appears in exception messages.
"""

import requests

from searchbot.exceptions import ShortenerError


def shorten(url: str, api_url: str, api_key: str, timeout: float = 5.0) -> str:
    """Create a short URL for ``url`` via the URL Shortener create API.

    Args:
        url: Absolute destination URL (passed through unmodified).
        api_url: Shortener base URL, e.g. ``"http://url-shortener:8080"``.
        api_key: Bearer token sent in the ``Authorization`` header.
        timeout: Per-request timeout in seconds.

    Returns:
        The short URL string from the response's ``url`` field.

    Raises:
        ShortenerError: On timeout, connection failure, any non-201 status,
            or a malformed response body. The message is log-oriented (never
            sent to IRC; never includes the API key).
    """
    endpoint = f"{api_url.rstrip('/')}/api/v1/links"
    # Content-Type is set automatically by requests when json= is passed.
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        resp = requests.post(endpoint, headers=headers, json={"url": url}, timeout=timeout)
    except requests.Timeout:
        raise ShortenerError("shortener timed out")
    except requests.ConnectionError:
        raise ShortenerError("shortener unreachable")

    if resp.status_code != 201:
        raise ShortenerError(f"shortener returned HTTP {resp.status_code}")

    try:
        short_url = resp.json()["url"]
    except (ValueError, KeyError, TypeError):
        raise ShortenerError("shortener returned a malformed response")
    if not isinstance(short_url, str) or not short_url:
        raise ShortenerError("shortener returned a malformed response")
    return short_url
