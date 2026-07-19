import json

import pytest
import requests
import responses as responses_lib

from searchbot.exceptions import ShortenerError
from searchbot.shortener import shorten

_SHORTENER_URL = "http://url-shortener:8080"
_CREATE_URL = "http://url-shortener:8080/api/v1/links"
_SHORT_URL = "https://short.example.com/a7K2xP"


@responses_lib.activate
def test_success_returns_url_field():
    responses_lib.add(
        responses_lib.POST,
        _CREATE_URL,
        json={"id": "a7K2xP", "url": _SHORT_URL},
        status=201,
    )
    assert shorten("https://example.com/long", _SHORTENER_URL, "test-key") == _SHORT_URL


@responses_lib.activate
def test_success_sends_bearer_auth_and_url_body():
    responses_lib.add(
        responses_lib.POST,
        _CREATE_URL,
        json={"id": "a7K2xP", "url": _SHORT_URL},
        status=201,
    )
    shorten("https://example.com/long", _SHORTENER_URL, "secret-key")
    request = responses_lib.calls[0].request
    assert request.headers["Authorization"] == "Bearer secret-key"
    assert request.headers["Content-Type"] == "application/json"
    body = request.body
    if isinstance(body, bytes):
        body = body.decode()
    assert json.loads(body) == {"url": "https://example.com/long"}


@pytest.mark.parametrize("status", [400, 401, 404, 429, 500, 502, 503, 504])
@responses_lib.activate
def test_non_201_raises(status):
    responses_lib.add(responses_lib.POST, _CREATE_URL, json={"error": "x"}, status=status)
    with pytest.raises(ShortenerError):
        shorten("https://example.com/long", _SHORTENER_URL, "test-key")


@responses_lib.activate
def test_timeout_raises():
    responses_lib.add(responses_lib.POST, _CREATE_URL, body=requests.Timeout())
    with pytest.raises(ShortenerError, match="timed out"):
        shorten("https://example.com/long", _SHORTENER_URL, "test-key")


@responses_lib.activate
def test_connection_error_raises():
    responses_lib.add(responses_lib.POST, _CREATE_URL, body=requests.ConnectionError())
    with pytest.raises(ShortenerError, match="unreachable"):
        shorten("https://example.com/long", _SHORTENER_URL, "test-key")


@responses_lib.activate
def test_malformed_body_raises():
    responses_lib.add(
        responses_lib.POST, _CREATE_URL, body="not json", status=201, content_type="text/plain"
    )
    with pytest.raises(ShortenerError, match="malformed"):
        shorten("https://example.com/long", _SHORTENER_URL, "test-key")


@responses_lib.activate
def test_missing_url_field_raises():
    responses_lib.add(responses_lib.POST, _CREATE_URL, json={"id": "a7K2xP"}, status=201)
    with pytest.raises(ShortenerError, match="malformed"):
        shorten("https://example.com/long", _SHORTENER_URL, "test-key")


@responses_lib.activate
def test_url_field_not_a_string_raises():
    responses_lib.add(responses_lib.POST, _CREATE_URL, json={"url": 123}, status=201)
    with pytest.raises(ShortenerError, match="malformed"):
        shorten("https://example.com/long", _SHORTENER_URL, "test-key")


@responses_lib.activate
def test_empty_url_field_raises():
    responses_lib.add(responses_lib.POST, _CREATE_URL, json={"url": ""}, status=201)
    with pytest.raises(ShortenerError, match="malformed"):
        shorten("https://example.com/long", _SHORTENER_URL, "test-key")


@responses_lib.activate
def test_non_dict_body_raises():
    responses_lib.add(responses_lib.POST, _CREATE_URL, json=["not", "a", "dict"], status=201)
    with pytest.raises(ShortenerError, match="malformed"):
        shorten("https://example.com/long", _SHORTENER_URL, "test-key")


@responses_lib.activate
def test_api_url_trailing_slash_stripped():
    responses_lib.add(
        responses_lib.POST,
        _CREATE_URL,
        json={"id": "a7K2xP", "url": _SHORT_URL},
        status=201,
    )
    # Registered URL has no trailing slash; the trailing slash on the base URL
    # must be stripped or the request would not match and would raise.
    shorten("https://example.com/long", "http://url-shortener:8080/", "test-key")
    assert len(responses_lib.calls) == 1


@responses_lib.activate
def test_no_retries_on_5xx():
    """The client must not retry internally — one failed POST = one request."""
    responses_lib.add(responses_lib.POST, _CREATE_URL, json={"error": "x"}, status=500)
    with pytest.raises(ShortenerError):
        shorten("https://example.com/long", _SHORTENER_URL, "test-key")
    assert len(responses_lib.calls) == 1


@responses_lib.activate
def test_no_retries_on_timeout():
    """A timeout must not trigger an internal retry."""
    responses_lib.add(responses_lib.POST, _CREATE_URL, body=requests.Timeout())
    with pytest.raises(ShortenerError):
        shorten("https://example.com/long", _SHORTENER_URL, "test-key")
    assert len(responses_lib.calls) == 1


@responses_lib.activate
def test_api_key_not_in_exception_message():
    responses_lib.add(responses_lib.POST, _CREATE_URL, status=500)
    with pytest.raises(ShortenerError) as exc_info:
        shorten("https://example.com/long", _SHORTENER_URL, "super-secret-key-do-not-leak")
    assert "super-secret-key-do-not-leak" not in str(exc_info.value)
