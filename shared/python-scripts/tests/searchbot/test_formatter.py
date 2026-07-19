from searchbot.formatter import format_results
from searchbot.models import SearchResult


def _r(title: str, url: str) -> SearchResult:
    return SearchResult(title=title, url=url)


def test_two_results():
    results = [
        _r("Rust Programming Language", "https://www.rust-lang.org/"),
        _r("The Rust Book", "https://doc.rust-lang.org/book/"),
    ]
    out = format_results(
        results, ["https://go.efnetmoto.com/a7K2", "https://go.efnetmoto.com/b91Q"]
    )
    assert out == [
        "1. Rust Programming Language — https://go.efnetmoto.com/a7K2",
        "2. The Rust Book — https://go.efnetmoto.com/b91Q",
    ]


def test_one_result():
    out = format_results([_r("Solo", "https://x")], ["https://s"])
    assert out == ["1. Solo — https://s"]


def test_zero_results():
    assert format_results([], []) == []


def test_uses_provided_urls_verbatim():
    """The formatter renders what it's given — it does not re-apply fallback.

    Call-site resolves shortener fallback before formatting; passing the
    original URL here must produce a line with that original URL unchanged.
    """
    out = format_results(
        [_r("T", "https://original.example/long")], ["https://original.example/long"]
    )
    assert out == ["1. T — https://original.example/long"]
