"""Format search results as IRC messages."""

from searchbot.models import SearchResult

# mIRC bold. Bolds the title so it leads the line; the only formatting
# attribute used (project policy: formatting-only, no color).
_BOLD = "\x02"
# Reads as "links to" — clearer than an em-dash for a URL. UTF-8 is safe: the
# bot already relied on UTF-8 for the old em-dash separator, so the transport
# is proven to carry it.
_ARROW = " → "


def format_results(results: list[SearchResult], short_urls: list[str]) -> list[str]:
    """Format results as one IRC line per result.

    Args:
        results: Brave results (title + domain + original URL).
        short_urls: Final display URL per result (short URL on success,
            original URL on shortener failure), parallel to ``results``.

    Returns:
        One IRC message body per result:
        ``"[<domain>] <bold>title<bold> → <url>"``. No index — results are
        not addressable by number (no ``!g 2`` to expand the Nth hit), so a
        numeric prefix would be decorative noise competing with the bolded
        title. Empty if ``results`` is empty — the caller owns the no-results
        message.

    Raises:
        ValueError: If ``results`` and ``short_urls`` differ in length. The two
            lists are parallel by contract; ``zip(..., strict=True)`` makes a
            caller bug a loud failure rather than silently dropping entries.
    """
    return [
        f"[{result.domain}] {_BOLD}{result.title}{_BOLD}{_ARROW}{url}"
        for result, url in zip(results, short_urls, strict=True)
    ]
