import pytest

from weather.models import Units, UserPref
from weather.prefs import _deserialize, _serialize, get_pref, set_pref


@pytest.fixture(autouse=True)
def reset_mock(eggdrop_mock):
    eggdrop_mock.tcl.setuser.reset_mock()
    eggdrop_mock.tcl.getuser.reset_mock()


@pytest.mark.parametrize(
    "pref, prefstring",
    [
        (UserPref("94025", metar=False, units=Units.METRIC), "94025"),
        (UserPref("KSFO", metar=True, units=Units.METRIC), "--metar KSFO"),
        (UserPref("94025", metar=False, units=Units.IMPERIAL), "--imperial 94025"),
        (UserPref("KSFO", metar=True, units=Units.IMPERIAL), "--metar --imperial KSFO"),
        (UserPref(None, metar=False, units=Units.IMPERIAL), "--imperial"),
        (UserPref(None, metar=False, units=Units.METRIC), ""),
        (UserPref("San Mateo, CA", metar=False, units=Units.METRIC), "San Mateo, CA"),
    ],
)
def test_serialize(pref, prefstring):
    assert _serialize(pref) == prefstring


@pytest.mark.parametrize(
    "prefstring, location, metar, units",
    [
        ("94025", "94025", False, Units.METRIC),
        ("--metar KSFO", "KSFO", True, Units.METRIC),
        ("--imperial 94025", "94025", False, Units.IMPERIAL),
        ("--metar --imperial KSFO", "KSFO", True, Units.IMPERIAL),
        ("--imperial", None, False, Units.IMPERIAL),
        ("San Mateo, CA", "San Mateo, CA", False, Units.METRIC),
    ],
)
def test_deserialize(prefstring, location, metar, units):
    result = _deserialize(prefstring)
    assert result.location == location
    assert result.metar is metar
    assert result.units == units


def test_deserialize_empty_returns_none():
    assert _deserialize("") is None


# Integration tests with mocked eggdrop calls
def test_get_pref_returns_none_when_absent(eggdrop_mock):
    eggdrop_mock.tcl.getuser.return_value = None
    assert get_pref("testuser") is None


def test_get_pref_returns_none_for_empty_string(eggdrop_mock):
    eggdrop_mock.tcl.getuser.return_value = ""
    assert get_pref("testuser") is None


def test_set_and_get_roundtrip(eggdrop_mock):
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
