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
        (
            UserPref("a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6", provider_id="awn"),
            "--awn a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        ),
        (
            UserPref("a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6", provider_id="awn", units=Units.IMPERIAL),
            "--awn --imperial a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        ),
        (
            UserPref("KSFO", metar=True, units=Units.IMPERIAL, provider_id=None),
            "--metar --imperial KSFO",
        ),
    ],
)
def test_serialize(pref, prefstring):
    assert _serialize(pref) == prefstring


@pytest.mark.parametrize(
    "prefstring, location, metar, units, provider_id",
    [
        ("94025", "94025", False, Units.METRIC, None),
        ("--metar KSFO", "KSFO", True, Units.METRIC, None),
        ("--imperial 94025", "94025", False, Units.IMPERIAL, None),
        ("--metar --imperial KSFO", "KSFO", True, Units.IMPERIAL, None),
        ("--imperial", None, False, Units.IMPERIAL, None),
        ("San Mateo, CA", "San Mateo, CA", False, Units.METRIC, None),
        (
            "--awn a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            False,
            Units.METRIC,
            "awn",
        ),
        (
            "--awn --imperial a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            False,
            Units.IMPERIAL,
            "awn",
        ),
        ("--aprs KK4LFC-13", "KK4LFC-13", False, Units.METRIC, "aprs"),
    ],
)
def test_deserialize(prefstring, location, metar, units, provider_id):
    result = _deserialize(prefstring)
    assert result.location == location
    assert result.metar is metar
    assert result.units == units
    assert result.provider_id == provider_id


def test_serialize_deserialize_provider_id_roundtrip():
    """Full round-trip through serialize → deserialize preserves provider_id."""
    pref = UserPref("aaaabbbbccccddddaaaabbbbccccdddd", provider_id="awn")
    restored = _deserialize(_serialize(pref))
    assert restored.provider_id == "awn"
    assert restored.location == "aaaabbbbccccddddaaaabbbbccccdddd"
    assert restored.metar is False
    assert restored.units == Units.METRIC


def test_deserialize_old_string_has_none_provider_id():
    """Pre-change stored strings (no --<id> token) deserialize with provider_id=None,
    ensuring backward compatibility for existing saved prefs."""
    result = _deserialize("--metar KSFO")
    assert result.provider_id is None


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
    assert result.provider_id is None


def test_set_and_get_roundtrip_with_provider_id(eggdrop_mock):
    stored = {}

    def mock_set(handle, field, key, val):
        stored[(handle, key)] = val

    def mock_get(handle, field, key):
        return stored.get((handle, key))

    eggdrop_mock.tcl.setuser.side_effect = mock_set
    eggdrop_mock.tcl.getuser.side_effect = mock_get

    pref = UserPref("aaaabbbbccccddddaaaabbbbccccdddd", provider_id="awn")
    set_pref("testuser", pref)
    result = get_pref("testuser")

    assert result.location == "aaaabbbbccccddddaaaabbbbccccdddd"
    assert result.provider_id == "awn"
    assert result.metar is False
    assert result.units == Units.METRIC
