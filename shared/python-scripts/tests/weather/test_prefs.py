import sys
from unittest.mock import MagicMock

import pytest

# Patch the eggdrop module before prefs.py is imported
eggdrop_mock = MagicMock()
sys.modules["eggdrop"] = eggdrop_mock
sys.modules["eggdrop.tcl"] = eggdrop_mock.tcl

from weather.models import Units, UserPref
from weather.prefs import _deserialize, _serialize, get_pref, set_pref


@pytest.fixture(autouse=True)
def reset_mock():
    eggdrop_mock.tcl.setuser.reset_mock()
    eggdrop_mock.tcl.getuser.reset_mock()


# Serialization round-trip tests (no eggdrop calls needed — test _serialize/_deserialize directly)


def test_serialize_simple_zip():
    assert _serialize(UserPref("94025", metar=False, units=Units.METRIC)) == "94025"


def test_serialize_metar():
    assert _serialize(UserPref("KSFO", metar=True, units=Units.METRIC)) == "--metar KSFO"


def test_serialize_imperial():
    assert _serialize(UserPref("94025", metar=False, units=Units.IMPERIAL)) == "--imperial 94025"


def test_serialize_metar_imperial():
    result = _serialize(UserPref("KSFO", metar=True, units=Units.IMPERIAL))
    assert result == "--metar --imperial KSFO"


def test_serialize_units_only_imperial():
    assert _serialize(UserPref(None, metar=False, units=Units.IMPERIAL)) == "--imperial"


def test_serialize_empty_pref():
    assert _serialize(UserPref(None, metar=False, units=Units.METRIC)) == ""


# Deserialization tests
def test_deserialize_simple_zip():
    p = _deserialize("94025")
    assert p.location == "94025"
    assert p.metar is False
    assert p.units == Units.METRIC


def test_deserialize_metar():
    p = _deserialize("--metar KSFO")
    assert p.location == "KSFO"
    assert p.metar is True
    assert p.units == Units.METRIC


def test_deserialize_imperial():
    p = _deserialize("--imperial 94025")
    assert p.location == "94025"
    assert p.units == Units.IMPERIAL


def test_deserialize_metar_imperial():
    p = _deserialize("--metar --imperial KSFO")
    assert p.location == "KSFO"
    assert p.metar is True
    assert p.units == Units.IMPERIAL


def test_deserialize_units_only():
    p = _deserialize("--imperial")
    assert p.location is None
    assert p.units == Units.IMPERIAL


def test_deserialize_empty_returns_none():
    assert _deserialize("") is None


def test_deserialize_city_state():
    # Location with spaces round-trips correctly
    p = _deserialize("San Mateo, CA")
    assert p.location == "San Mateo, CA"


# Integration tests with mocked eggdrop calls
def test_get_pref_returns_none_when_absent():
    eggdrop_mock.tcl.getuser.return_value = None
    assert get_pref("testuser") is None


def test_get_pref_returns_none_for_empty_string():
    eggdrop_mock.tcl.getuser.return_value = ""
    assert get_pref("testuser") is None


def test_set_and_get_roundtrip():
    stored = {}

    def mock_set(handle, field, key, val):
        stored[(handle, key)] = val

    def mock_get(handle, field, key):
        return stored.get((handle, key))

    eggdrop_mock.tcl.setuser.side_effect = mock_set
    eggdrop_mock.tcl.getuser.side_effect = mock_get

    pref = UserPref("KSFO", metar=True, units=Units.IMPERIAL)
    set_pref("testuser", pref)
    result = get_pref("testuser")

    assert result.location == "KSFO"
    assert result.metar is True
    assert result.units == Units.IMPERIAL
