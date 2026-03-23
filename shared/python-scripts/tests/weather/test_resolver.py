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


def test_icao_known_prefix():
    r = classify("KSFO")
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
