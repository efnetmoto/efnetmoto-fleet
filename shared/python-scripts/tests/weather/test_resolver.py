import pytest

from weather.exceptions import ResolverError
from weather.models import LocationType
from weather.resolver import classify


def test_zip_5digit():
    r = classify("94025")
    assert r.type == LocationType.ZIP
    assert r.query == "94025"


def test_zip_9digit():
    r = classify("94025-1234")
    assert r.type == LocationType.ZIP


def test_city_state():
    r = classify("San Mateo, CA")
    assert r.type == LocationType.CITY_STATE


def test_iata_known():
    r = classify("SFO")
    assert r.type == LocationType.IATA


def test_iata_unknown_3char():
    # XYZ: 3 chars but not in IATA set — falls through to CITY_STATE
    r = classify("XYZ")
    assert r.type == LocationType.CITY_STATE


def test_icao_known_alpha_prefix():
    r = classify("KSFO")
    assert r.type == LocationType.ICAO


def test_icao_known_alnum_prefix():
    r = classify("K0S9")
    assert r.type == LocationType.ICAO


def test_icao_unknown_prefix():
    # ZZZZ: 4 chars but "Z" IS a valid ICAO prefix (China) — should be ICAO
    r = classify("ZZZZ")
    assert r.type == LocationType.ICAO


def test_4char_invalid_icao_prefix():
    # XSFO: 4 chars, "X" is not a known ICAO prefix — falls to CITY_STATE
    r = classify("XSFO")
    assert r.type == LocationType.CITY_STATE


def test_empty_string():
    with pytest.raises(ResolverError):
        classify("")


def test_whitespace_only():
    with pytest.raises(ResolverError):
        classify("   ")


def test_lowercase_normalized():
    # Input is lowercased but should match IATA after normalization
    r = classify("sfo")
    assert r.type == LocationType.IATA


def test_raw_preserved():
    r = classify("San Mateo, CA")
    assert r.raw == "San Mateo, CA"


def test_query_normalized():
    r = classify("sfo")
    assert r.query == "SFO"


def test_ambient_slug():
    r = classify("3602d35f96fb9f73b9f34c87a0279116")
    assert r.type == LocationType.AMBIENT_SLUG


def test_ambient_url_https():
    r = classify("https://ambientweather.net/dashboard/3602d35f96fb9f73b9f34c87a0279116")
    assert r.type == LocationType.AMBIENT_URL
    assert r.query == "3602d35f96fb9f73b9f34c87a0279116"


def test_ambient_url_http():
    r = classify("http://ambientweather.net/dashboard/3602d35f96fb9f73b9f34c87a0279116")
    assert r.type == LocationType.AMBIENT_URL
    assert r.query == "3602d35f96fb9f73b9f34c87a0279116"


def test_ambient_url_query_is_bare_slug():
    url = "https://ambientweather.net/dashboard/3602d35f96fb9f73b9f34c87a0279116"
    r = classify(url)
    assert r.query == "3602d35f96fb9f73b9f34c87a0279116"
    assert r.raw == url


def test_uppercase_32char_not_ambient_slug():
    # 32 chars but uppercase — not a valid slug
    r = classify("ABCD1234ABCD1234ABCD1234ABCD1234")
    assert r.type == LocationType.CITY_STATE


def test_31char_hex_not_ambient_slug():
    # 31 chars — too short
    r = classify("3602d35f96fb9f73b9f34c87a027911")
    assert r.type == LocationType.CITY_STATE


def test_aprs_callsign():
    valid_callsigns = [
        "K1A-13",  # 1×1
        "K1AB-13",  # 1×2
        "K1ABC-13",  # 1×3
        "KK1A-13",  # 2×1
        "KK1AB-13",  # 2×2
        "KK1ABC-13",  # 2×3
    ]
    for call in valid_callsigns:
        r = classify(call)
        assert r.type == LocationType.APRS


def test_aprs_bad_callsigns():
    invalid_cwop_callsigns = [
        "K1A",  # missing SSID
        "K1A-1",  # wrong SSID (not -13)
        "K1A-013",  # leading zero in SSID
        "K1A-130",  # SSID too long
        "K1A--13",  # double dash
        "K1A-13-1",  # extra suffix
        "K1-13",  # missing suffix letter
        "K11-13",  # suffix does not end in letter
        "K1AB1-13",  # suffix ends in digit
        "KKK1ABC-13",  # prefix too long (3 letters)
        "K-1ABC-13",  # malformed prefix
        "2E-13",  # missing suffix
        "2E1A1-13",  # suffix ends in digit
        "A21B-13",  # suffix too short
        "A2!BC-13",  # invalid character
        "K1ABC_13",  # wrong separator
        "K1ABC/13",  # wrong separator
    ]
    for call in invalid_cwop_callsigns:
        r = classify(call)
        assert r.type != LocationType.APRS
