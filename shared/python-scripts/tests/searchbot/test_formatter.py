from searchbot.formatter import format_results
from searchbot.models import SearchResult

_BOLD = "\x02"


def _r(title: str, url: str, domain: str) -> SearchResult:
    return SearchResult(title=title, url=url, domain=domain)


def test_two_results():
    results = [
        _r("Rust Programming Language", "https://www.rust-lang.org/", "rust-lang.org"),
        _r("The Rust Book", "https://doc.rust-lang.org/book/", "doc.rust-lang.org"),
    ]
    out = format_results(
        results, ["https://go.efnetmoto.com/a7K2", "https://go.efnetmoto.com/b91Q"]
    )
    assert out == [
        (
            f"[rust-lang.org] {_BOLD}Rust Programming Language{_BOLD}"
            " → https://go.efnetmoto.com/a7K2"
        ),
        (f"[doc.rust-lang.org] {_BOLD}The Rust Book{_BOLD} → https://go.efnetmoto.com/b91Q"),
    ]


def test_one_result():
    out = format_results([_r("Solo", "https://x", "x")], ["https://s"])
    assert out == [f"[x] {_BOLD}Solo{_BOLD} → https://s"]


def test_zero_results():
    assert format_results([], []) == []


def test_uses_provided_urls_verbatim():
    """The formatter renders what it's given — it does not re-apply fallback.

    Call-site resolves shortener fallback before formatting; passing the
    original URL here must produce a line with that original URL unchanged.
    The domain is taken from the result, not the display URL, so a short
    display URL must not leak into the domain tag.
    """
    out = format_results(
        [_r("T", "https://original.example/long", "original.example")],
        ["https://original.example/long"],
    )
    assert out == [f"[original.example] {_BOLD}T{_BOLD} → https://original.example/long"]


def test_domain_taken_from_result_not_display_url():
    """The domain tag comes from ``result.domain`` (the original URL's host),
    never from the short display URL — that's the whole point of carrying
    domain on the model: it re-surfaces the source the shortener erased.
    """
    out = format_results(
        [_r("T", "https://real.example/page", "real.example")],
        ["https://go.efnetmoto.com/a7K2"],
    )
    assert out == [f"[real.example] {_BOLD}T{_BOLD} → https://go.efnetmoto.com/a7K2"]
