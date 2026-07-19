import json

import pytest
import requests
import responses as responses_lib

from searchbot.brave import search
from searchbot.exceptions import BraveError

_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


@pytest.fixture
def two_results(fixtures_dir):
    return json.loads((fixtures_dir / "brave_two_results.json").read_text())


@pytest.fixture
def one_result(fixtures_dir):
    return json.loads((fixtures_dir / "brave_one_result.json").read_text())


@pytest.fixture
def zero_results(fixtures_dir):
    return json.loads((fixtures_dir / "brave_zero_results.json").read_text())


@responses_lib.activate
def test_two_results(two_results):
    responses_lib.add(responses_lib.GET, _BRAVE_URL, json=two_results, status=200)
    results = search("rust async", "test-key")
    assert len(results) == 2
    assert results[0].title == "Rust Programming Language"
    assert results[0].url == "https://www.rust-lang.org/"
    assert results[1].title == "The Rust Book"
    assert results[1].url == "https://doc.rust-lang.org/book/"


@responses_lib.activate
def test_one_result(one_result):
    responses_lib.add(responses_lib.GET, _BRAVE_URL, json=one_result, status=200)
    results = search("rust", "test-key")
    assert len(results) == 1
    assert results[0].title == "Rust Programming Language"


@responses_lib.activate
def test_zero_results(zero_results):
    responses_lib.add(responses_lib.GET, _BRAVE_URL, json=zero_results, status=200)
    assert search("nonsense query xyz", "test-key") == []


@responses_lib.activate
def test_missing_web_key_returns_empty():
    responses_lib.add(responses_lib.GET, _BRAVE_URL, json={"query": "x"}, status=200)
    assert search("x", "test-key") == []


@responses_lib.activate
def test_missing_results_key_returns_empty():
    responses_lib.add(responses_lib.GET, _BRAVE_URL, json={"web": {}}, status=200)
    assert search("x", "test-key") == []


@responses_lib.activate
def test_count_caps_results(two_results):
    responses_lib.add(responses_lib.GET, _BRAVE_URL, json=two_results, status=200)
    results = search("rust", "test-key", count=1)
    assert len(results) == 1


@responses_lib.activate
def test_query_and_count_params_sent_to_brave(two_results):
    responses_lib.add(responses_lib.GET, _BRAVE_URL, json=two_results, status=200)
    search("rust async", "test-key", count=2)
    request_url = responses_lib.calls[0].request.url
    assert "q=" in request_url
    assert "count=2" in request_url


@responses_lib.activate
def test_subscription_token_header_sent():
    responses_lib.add(responses_lib.GET, _BRAVE_URL, json={"web": {"results": []}}, status=200)
    search("x", "secret-key")
    assert responses_lib.calls[0].request.headers["X-Subscription-Token"] == "secret-key"


@responses_lib.activate
def test_timeout_raises_brave_error():
    responses_lib.add(responses_lib.GET, _BRAVE_URL, body=requests.Timeout())
    with pytest.raises(BraveError, match="timed out"):
        search("x", "test-key")


@responses_lib.activate
def test_connection_error_raises_brave_error():
    responses_lib.add(responses_lib.GET, _BRAVE_URL, body=requests.ConnectionError())
    with pytest.raises(BraveError, match="temporarily unavailable"):
        search("x", "test-key")


@responses_lib.activate
def test_non_200_raises_brave_error():
    responses_lib.add(responses_lib.GET, _BRAVE_URL, json={"error": "rate limited"}, status=429)
    with pytest.raises(BraveError, match="temporarily unavailable"):
        search("x", "test-key")


@responses_lib.activate
def test_malformed_json_raises_brave_error():
    responses_lib.add(
        responses_lib.GET, _BRAVE_URL, body="not json", status=200, content_type="text/plain"
    )
    with pytest.raises(BraveError, match="temporarily unavailable"):
        search("x", "test-key")


# All remaining malformed-shape cases surface the same user-safe message, so
# they collapse into one parametrized test. Each id names the branch it hits.
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(["not", "a", "dict"], id="non_dict_body"),
        pytest.param({"web": {"results": "oops"}}, id="results_not_a_list"),
        pytest.param({"web": {"results": ["not a dict"]}}, id="result_not_a_dict"),
        pytest.param({"web": {"results": [{"title": "no url"}]}}, id="result_missing_url"),
    ],
)
@responses_lib.activate
def test_malformed_body_raises_brave_error(body):
    responses_lib.add(responses_lib.GET, _BRAVE_URL, json=body, status=200)
    with pytest.raises(BraveError, match="temporarily unavailable"):
        search("x", "test-key")


@responses_lib.activate
def test_api_key_not_in_exception_message():
    responses_lib.add(responses_lib.GET, _BRAVE_URL, status=500)
    with pytest.raises(BraveError) as exc_info:
        search("x", "super-secret-key-do-not-leak")
    assert "super-secret-key-do-not-leak" not in str(exc_info.value)


@responses_lib.activate
def test_result_domain_strips_www(two_results):
    responses_lib.add(responses_lib.GET, _BRAVE_URL, json=two_results, status=200)
    results = search("rust", "test-key")
    assert results[0].domain == "rust-lang.org"
    assert results[1].domain == "doc.rust-lang.org"


@pytest.mark.parametrize(
    "url,expected_domain",
    [
        pytest.param("https://www.example.com/page", "example.com", id="strips_www"),
        pytest.param("https://example.com/page", "example.com", id="no_www"),
        pytest.param("https://sub.example.com/", "sub.example.com", id="keeps_subdomain"),
        pytest.param("https://example.com:8443/x", "example.com", id="strips_port"),
        pytest.param("not-a-url", "not-a-url", id="malformed_falls_back_to_raw"),
    ],
)
@responses_lib.activate
def test_result_domain_extracted_from_url(url, expected_domain):
    responses_lib.add(
        responses_lib.GET,
        _BRAVE_URL,
        json={"web": {"results": [{"title": "T", "url": url}]}},
        status=200,
    )
    results = search("x", "test-key")
    assert results[0].domain == expected_domain
