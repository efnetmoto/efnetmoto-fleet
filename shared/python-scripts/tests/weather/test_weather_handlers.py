# Tests for handler functions in weather.py (the eggdrop entry point).
# eggdrop from-imports (putserv, putlog, bind, validuser) are mocked; weather.py is loaded by
# file path via importlib because `import weather` resolves to the weather/ package.

import importlib.util
import os
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

# Install a fresh eggdrop mock — force-assign so other test modules that ran earlier
# (e.g. test_prefs.py) don't leave a stale mock in sys.modules before exec_module runs.
_eggdrop_mock = MagicMock()
sys.modules["eggdrop"] = _eggdrop_mock
sys.modules["eggdrop.tcl"] = _eggdrop_mock.tcl

# Wire our named mocks into the eggdrop mock so from-imports in weather.py resolve
# to the exact objects these tests assert on.
_putserv = MagicMock()
_putlog = MagicMock()
_bind = MagicMock(return_value=MagicMock())
_validuser = MagicMock(return_value=1)
_eggdrop_mock.bind = _bind
_eggdrop_mock.tcl.putserv = _putserv
_eggdrop_mock.tcl.putlog = _putlog
_eggdrop_mock.tcl.validuser = _validuser

# WEATHERAPI_KEY must be set before weather.py is imported (WeatherAPIProvider checks at init)
os.environ.setdefault("WEATHERAPI_KEY", "test-key")

# Load weather.py by file path — `import weather` would resolve to the weather/ package
_script_path = pathlib.Path(__file__).parents[2] / "weather.py"
_spec = importlib.util.spec_from_file_location("weather_script", _script_path)
w = importlib.util.module_from_spec(_spec)
sys.modules["weather_script"] = w
_spec.loader.exec_module(w)


@pytest.fixture(autouse=True)
def reset_mocks():
    _putserv.reset_mock()
    _putlog.reset_mock()
    _validuser.reset_mock()
    _validuser.return_value = 1  # registered by default


# handle_wzset — unrecognized user


def test_wzset_unregistered_user_blocked():
    w.handle_wzset("SomeNick", "host@example.com", "*", "#moto", "94025")
    _putserv.assert_called_once()
    msg = _putserv.call_args[0][0]
    assert "registered bot user" in msg
    assert ".wzhelp" in msg


def test_wzset_flags_only_unregistered_user_blocked():
    """Flags-only path (.wzset --imperial) must also be blocked before any pref logic."""
    w.handle_wzset("SomeNick", "host@example.com", "*", "#moto", "--imperial")
    _putserv.assert_called_once()
    msg = _putserv.call_args[0][0]
    assert "registered bot user" in msg


# handle_wz — unrecognized user


def test_wz_no_args_unregistered_user_blocked():
    w.handle_wz("SomeNick", "host@example.com", "*", "#moto", "")
    _putserv.assert_called_once()
    msg = _putserv.call_args[0][0]
    assert "registered with the bot" in msg
    assert ".wz <location>" in msg


def test_wz_with_location_unregistered_user_allowed():
    """Ad-hoc .wz <location> must work for unrecognized users — no registration guard."""
    with (
        patch.object(w._router, "route", side_effect=Exception("stop here")),
        patch.object(w.resolver, "classify", return_value=MagicMock()),
    ):
        w.handle_wz("SomeNick", "host@example.com", "*", "#moto", "94025")
        msg = _putserv.call_args[0][0]
        assert "registered" not in msg


# handle_wz --user flag


def test_wz_user_registered_with_location():
    """--user foo fetches weather for foo's saved location."""
    from weather.models import Units, UserPref

    pref = UserPref(location="Denver, CO", metar=False, units=Units.METRIC)
    with (
        patch.object(w.prefs, "get_pref", return_value=pref),
        patch.object(w.resolver, "classify", return_value=MagicMock()) as mock_classify,
        patch.object(w._router, "route", side_effect=Exception("stop here")),
    ):
        w.handle_wz("AskingNick", "host@example.com", "*", "#moto", "--user foo")
        mock_classify.assert_called_once_with("Denver, CO")


def test_wz_user_not_registered():
    """--user foo where foo is unknown reports an error in channel."""
    _validuser.return_value = 0
    w.handle_wz("AskingNick", "host@example.com", "*", "#moto", "--user foo")
    _putserv.assert_called_once()
    msg = _putserv.call_args[0][0]
    assert "foo" in msg
    assert "not registered" in msg


def test_wz_user_registered_no_location():
    """--user foo where foo has no saved location reports an error in channel."""
    from weather.models import Units, UserPref

    pref = UserPref(location=None, metar=False, units=Units.METRIC)
    with patch.object(w.prefs, "get_pref", return_value=pref):
        w.handle_wz("AskingNick", "host@example.com", "*", "#moto", "--user foo")
    _putserv.assert_called_once()
    msg = _putserv.call_args[0][0]
    assert "foo" in msg
    assert "no default location" in msg


def test_wz_user_with_explicit_imperial_overrides_pref():
    """--user foo --imperial uses foo's location but imperial units regardless of foo's pref."""
    from weather.models import Units, UserPref

    pref = UserPref(location="94025", metar=False, units=Units.METRIC)
    with (
        patch.object(w.prefs, "get_pref", return_value=pref),
        patch.object(w, "_do_fetch_weather") as mock_fetch,
    ):
        w.handle_wz("AskingNick", "host@example.com", "*", "#moto", "--user foo --imperial")
    mock_fetch.assert_called_once()
    # units is the 4th positional arg (index 3): nick, handle, metar, units, ...
    assert mock_fetch.call_args[0][3] == Units.IMPERIAL


def test_wz_user_combined_with_location_rejected():
    """--user foo Denver is rejected — cannot combine --user with a location query."""
    w.handle_wz("AskingNick", "host@example.com", "*", "#moto", "--user foo Denver")
    _putserv.assert_called_once()
    msg = _putserv.call_args[0][0]
    assert "--user cannot be combined" in msg
