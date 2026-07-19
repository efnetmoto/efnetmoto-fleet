"""Exceptions for the searchbot package.

``BraveError`` messages are user-safe: the entry point sends ``str(error)``
directly to IRC on a Brave failure.

``ShortenerError`` messages are log-oriented (they may include the shortener's
HTTP status); the entry point logs them and falls back to the original URL
rather than surfacing them to IRC.
"""


class BraveError(Exception):
    """Raised on any upstream Brave failure (timeout, non-200, malformed JSON).

    The message string is user-safe and may be sent to IRC.
    """


class ShortenerError(Exception):
    """Raised on any URL-shortener failure.

    The message string is for logs only — callers fall back to the original
    URL rather than surfacing this to IRC, so a shortener outage never blocks
    a search result.
    """
