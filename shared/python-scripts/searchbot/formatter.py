"""Format search results as IRC messages."""

from searchbot.models import SearchResult

# Em dash with surrounding spaces, matching the result-line format "1. <title> — <url>".
_SEPARATOR = " — "


def format_results(results: list[SearchResult], short_urls: list[str]) -> list[str]:
    """Format results as one numbered IRC line per result.

    Args:
        results: Brave results (title + original URL).
        short_urls: Final display URL per result (short URL on success,
            original URL on shortener failure), parallel to ``results``.

    Returns:
        One IRC message body per result, 1-indexed: ``"1. <title> — <url>"``.
        Empty if ``results`` is empty — the caller owns the no-results message.

    Raises:
        ValueError: If ``results`` and ``short_urls`` differ in length. The two
            lists are parallel by contract; ``zip(..., strict=True)`` makes a
            caller bug a loud failure rather than silently dropping entries.
    """
    return [
        f"{i}. {result.title}{_SEPARATOR}{url}"
        for i, (result, url) in enumerate(zip(results, short_urls, strict=True), start=1)
    ]
