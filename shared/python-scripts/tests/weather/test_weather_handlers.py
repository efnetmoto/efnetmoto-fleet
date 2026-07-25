# Tests for handler functions in weather.py (the eggdrop entry point).
# eggdrop from-imports (putserv, putlog, bind, validuser) are mocked; weather.py is loaded by
# file path via importlib because `import weather` resolves to the weather/ package.

import importlib.util
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

from weather.exceptions import ProviderError
from weather.models import Units, UserPref

# conftest.py installs the eggdrop mock before any test file is imported.
# Wire named mocks onto it so from-imports in weather.py resolve to the exact
# objects these tests assert on. These must be module-level: exec_module below
# binds weather.py's local names to these objects at import time, so creating
# fresh mocks per-test in fixtures would not be seen by weather.py's functions.
_eggdrop_mock = sys.modules["eggdrop"]
_putserv = MagicMock()
_putlog = MagicMock()
_bind = MagicMock(return_value=MagicMock())
_validuser = MagicMock(return_value="1")  # eggdrop's TCL validuser returns "1"/"0" as strings
_eggdrop_mock.bind = _bind
_eggdrop_mock.tcl.putserv = _putserv
_eggdrop_mock.tcl.putlog = _putlog
_eggdrop_mock.tcl.validuser = _validuser

# Load weather.py by file path — `import weather` would resolve to the weather/ package
_script_path = pathlib.Path(__file__).parents[2] / "weather.py"
_spec = importlib.util.spec_from_file_location("weather_script", _script_path)
w = importlib.util.module_from_spec(_spec)
sys.modules["weather_script"] = w
_spec.loader.exec_module(w)


@pytest.fixture
def putserv_mock():
    return _putserv


@pytest.fixture
def putlog_mock():
    return _putlog


@pytest.fixture
def validuser_mock():
    return _validuser


@pytest.fixture(autouse=True)
def reset_mocks(putserv_mock, putlog_mock, validuser_mock):
    putserv_mock.reset_mock()
    putlog_mock.reset_mock()
    validuser_mock.reset_mock()
    validuser_mock.return_value = "1"  # registered by default (string, as eggdrop returns)


# handle_wzset — unrecognized user


def test_wzset_unregistered_user_blocked(putserv_mock):
    w.handle_wzset("SomeNick", "host@example.com", "*", "#moto", "94025")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "registered bot user" in msg
    assert "docs/user/weather/#getting-registered" in msg


def test_wzset_flags_only_unregistered_user_blocked(putserv_mock):
    """Flags-only path (.wzset --imperial) must also be blocked before any pref logic."""
    w.handle_wzset("SomeNick", "host@example.com", "*", "#moto", "--imperial")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "registered bot user" in msg


# handle_wz — unrecognized user


def test_wz_no_args_unregistered_user_blocked(putserv_mock):
    w.handle_wz("SomeNick", "host@example.com", "*", "#moto", "")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "registered with the bot" in msg
    assert "docs/user/weather/#getting-registered" in msg


def test_wz_with_location_unregistered_user_allowed(putserv_mock):
    """Ad-hoc .wz <location> must work for unrecognized users — no registration guard."""
    with (
        patch.object(w._router, "route", side_effect=Exception("stop here")),
        patch.object(w.resolver, "classify", return_value=MagicMock()),
    ):
        w.handle_wz("SomeNick", "host@example.com", "*", "#moto", "94025")
        msg = putserv_mock.call_args[0][0]
        assert "registered" not in msg


# handle_wz --user flag


def test_wz_user_registered_with_location():
    """--user foo fetches weather for foo's saved location."""
    pref = UserPref(location="Denver, CO", metar=False, units=Units.METRIC)
    with (
        patch.object(w.prefs, "get_pref", return_value=pref),
        patch.object(w.resolver, "classify", return_value=MagicMock()) as mock_classify,
        patch.object(w._router, "route", side_effect=Exception("stop here")),
    ):
        w.handle_wz("AskingNick", "host@example.com", "*", "#moto", "--user foo")
        mock_classify.assert_called_once_with("Denver, CO")


def test_wz_user_not_registered(validuser_mock, putserv_mock):
    """--user foo where foo is unknown reports an error in channel.

    eggdrop's TCL validuser returns the string "0" for unknown handles; the guard
    must coerce via int() because `not "0"` is False in Python.
    """
    validuser_mock.return_value = "0"
    w.handle_wz("AskingNick", "host@example.com", "*", "#moto", "--user foo")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "foo" in msg
    assert "not registered" in msg


def test_wz_user_registered_no_location(putserv_mock):
    """--user foo where foo has no saved location reports an error in channel."""
    pref = UserPref(location=None, metar=False, units=Units.METRIC)
    with patch.object(w.prefs, "get_pref", return_value=pref):
        w.handle_wz("AskingNick", "host@example.com", "*", "#moto", "--user foo")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "foo" in msg
    assert "no default location" in msg


def test_wz_user_with_explicit_imperial_overrides_pref():
    """--user foo --imperial uses foo's location but imperial units regardless of foo's pref."""
    pref = UserPref(location="94025", metar=False, units=Units.METRIC)
    with (
        patch.object(w.prefs, "get_pref", return_value=pref),
        patch.object(w, "_do_fetch_weather") as mock_fetch,
    ):
        w.handle_wz("AskingNick", "host@example.com", "*", "#moto", "--user foo --imperial")
    mock_fetch.assert_called_once()
    # units is the 3rd positional arg (index 2): handle, metar, units, ...
    assert mock_fetch.call_args[0][2] == Units.IMPERIAL


def test_wz_user_combined_with_location_rejected(putserv_mock):
    """--user foo Denver is rejected — cannot combine --user with a location query."""
    w.handle_wz("AskingNick", "host@example.com", "*", "#moto", "--user foo Denver")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "--user cannot be combined" in msg


def test_wz_conflicting_unit_flags_rejected(putserv_mock):
    """--metric and --imperial together are rejected in handle_wz."""
    w.handle_wz("SomeNick", "host@example.com", "somehandle", "#moto", "--metric --imperial 94025")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "--metric or --imperial, not both" in msg


def test_wzset_conflicting_unit_flags_rejected(putserv_mock):
    """--metric and --imperial together are rejected in handle_wzset."""
    w.handle_wzset(
        "SomeNick", "host@example.com", "somehandle", "#moto", "--metric --imperial 94025"
    )
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "--metric or --imperial, not both" in msg


def test_wzset_empty_text_shows_usage(putserv_mock):
    w.handle_wzset("SomeNick", "host@example.com", "somehandle", "#moto", "")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "Usage:" in msg
    assert ".wzset" in msg


def test_wzset_metar_without_location_rejected(putserv_mock):
    """--metar with no location is rejected with an actionable error."""
    w.handle_wzset("SomeNick", "host@example.com", "somehandle", "#moto", "--metar")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "--metar requires an ICAO code" in msg


def test_wzset_metar_with_non_icao_location_rejected(putserv_mock):
    """--metar with a ZIP code is rejected — only valid with ICAO."""
    w.handle_wzset("SomeNick", "host@example.com", "somehandle", "#moto", "--metar 94025")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "--metar is only valid with ICAO codes" in msg


def test_wzset_units_only_update(putserv_mock):
    """--imperial with no location updates the units on the saved pref."""
    with (
        patch.object(w.prefs, "get_pref", return_value=None),
        patch.object(w.prefs, "set_pref") as mock_set,
    ):
        w.handle_wzset("SomeNick", "host@example.com", "somehandle", "#moto", "--imperial")
    mock_set.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "Preference updated" in msg
    assert "--imperial" in msg


def test_wzset_saves_location(putserv_mock):
    """A valid location is saved and a confirmation is sent."""
    mock_provider = MagicMock()
    with (
        patch.object(w._router, "route", return_value=mock_provider),
        patch.object(w.prefs, "get_pref", return_value=None),
        patch.object(w.prefs, "set_pref") as mock_set,
    ):
        w.handle_wzset("SomeNick", "host@example.com", "somehandle", "#moto", "94025")
    mock_set.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "Default set to" in msg
    assert "94025" in msg


def test_wzset_provider_route_error_rejected(putserv_mock):
    """Route error (e.g. unsupported location type) prevents saving with actionable feedback."""
    with (
        patch.object(w._router, "route", side_effect=ProviderError("bad location")),
        patch.object(w.prefs, "set_pref") as mock_set,
    ):
        w.handle_wzset("SomeNick", "host@example.com", "somehandle", "#moto", "94025")
    mock_set.assert_not_called()
    msg = putserv_mock.call_args[0][0]
    assert "bad location" in msg
    assert "Location not saved" in msg
    assert ".wzset" in msg


def test_wzset_provider_fetch_error_rejected(putserv_mock):
    """get_weather() failure (e.g. location not found) prevents saving with actionable feedback."""
    mock_provider = MagicMock()
    mock_provider.get_weather.side_effect = ProviderError("location not found")
    with (
        patch.object(w._router, "route", return_value=mock_provider),
        patch.object(w.prefs, "set_pref") as mock_set,
    ):
        w.handle_wzset("SomeNick", "host@example.com", "somehandle", "#moto", "94025")
    mock_set.assert_not_called()
    msg = putserv_mock.call_args[0][0]
    assert "location not found" in msg
    assert "Location not saved" in msg
    assert ".wzset" in msg


def test_wz_no_args_registered_no_pref(putserv_mock):
    """Registered user with no saved pref is directed to .wzset."""
    with patch.object(w.prefs, "get_pref", return_value=None):
        w.handle_wz("SomeNick", "host@example.com", "somehandle", "#moto", "")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "No default set" in msg
    assert ".wzset" in msg


def test_wz_no_args_registered_no_location(putserv_mock):
    """Registered user with a units-only pref (no location) is directed to .wzset."""
    pref = UserPref(location=None, metar=False, units=Units.IMPERIAL)
    with patch.object(w.prefs, "get_pref", return_value=pref):
        w.handle_wz("SomeNick", "host@example.com", "somehandle", "#moto", "")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert "No default location set" in msg
    assert ".wzset" in msg


def test_wz_no_args_registered_with_default():
    """Registered user with no args uses their saved default location."""
    pref = UserPref(location="94025", metar=False, units=Units.METRIC)
    with (
        patch.object(w.prefs, "get_pref", return_value=pref),
        patch.object(w.resolver, "classify", return_value=MagicMock()) as mock_classify,
        patch.object(w._router, "route", side_effect=Exception("stop here")),
    ):
        w.handle_wz("SomeNick", "host@example.com", "somehandle", "#moto", "")
    mock_classify.assert_called_once_with("94025")


def test_wzhelp_sends_pm_lines(putserv_mock):
    """Each help line is PMed to nick; channel receives a confirmation."""
    w.handle_wzhelp("SomeNick", "host@example.com", "somehandle", "#moto")
    assert putserv_mock.call_count == len(w.HELP_LINES) + 1
    for call in putserv_mock.call_args_list[:-1]:
        assert "PRIVMSG SomeNick :" in call[0][0]
    final_msg = putserv_mock.call_args_list[-1][0][0]
    assert "PRIVMSG #moto :" in final_msg
    assert "help sent via PM" in final_msg


# PM-bind adapters: handle_wz_msg / handle_wzset_msg / handle_wzhelp_msg


def test_wz_msg_replies_to_nick_no_prefix(putserv_mock):
    """PM invocation: reply target is the nick, no 'nick: ' prefix on errors."""
    with patch.object(w.prefs, "get_pref", return_value=None):
        w.handle_wz_msg("SomeNick", "host@example.com", "somehandle", "")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert msg.startswith("PRIVMSG SomeNick :")
    body = msg.split(":", 1)[1]
    assert not body.startswith("SomeNick:")  # no nick prefix in PM
    assert "No default set" in msg


def test_wz_msg_with_location_unregistered_user_allowed():
    """Ad-hoc PM .wz <location> reaches the resolver for unregistered users."""
    with (
        patch.object(w._router, "route", side_effect=Exception("stop here")),
        patch.object(w.resolver, "classify", return_value=MagicMock()) as mock_classify,
    ):
        w.handle_wz_msg("SomeNick", "host@example.com", "*", "94025")
    mock_classify.assert_called_once_with("94025")


def test_wz_msg_user_flag_rejected(putserv_mock):
    """--user is channel-only; in PM, return a clear error to the user."""
    w.handle_wz_msg("AskingNick", "host@example.com", "somehandle", "--user foo")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert msg.startswith("PRIVMSG AskingNick :")
    assert "--user only works in a channel" in msg


def test_wz_msg_conflicting_unit_flags_rejected(putserv_mock):
    """Flag-parse errors in PM go to the nick with no prefix."""
    w.handle_wz_msg("SomeNick", "host@example.com", "somehandle", "--metric --imperial 94025")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert msg.startswith("PRIVMSG SomeNick :")
    assert "--metric or --imperial, not both" in msg


def test_wzset_msg_unregistered_user_blocked(putserv_mock):
    """PM .wzset for unregistered user is blocked, error goes to PM."""
    w.handle_wzset_msg("SomeNick", "host@example.com", "*", "94025")
    putserv_mock.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert msg.startswith("PRIVMSG SomeNick :")
    assert "registered bot user" in msg


def test_wzset_msg_saves_location(putserv_mock):
    """PM .wzset <location> saves and confirms via PM, no nick prefix on the confirmation."""
    mock_provider = MagicMock()
    with (
        patch.object(w._router, "route", return_value=mock_provider),
        patch.object(w.prefs, "get_pref", return_value=None),
        patch.object(w.prefs, "set_pref") as mock_set,
    ):
        w.handle_wzset_msg("SomeNick", "host@example.com", "somehandle", "94025")
    mock_set.assert_called_once()
    msg = putserv_mock.call_args[0][0]
    assert msg.startswith("PRIVMSG SomeNick :")
    assert "Default set to" in msg
    assert "94025" in msg
    # No 'SomeNick: ' prefix on the body
    body = msg.split(":", 1)[1]
    assert not body.startswith("SomeNick:")


def test_wzhelp_msg_no_channel_echo(putserv_mock):
    """PM .wzhelp sends help lines only — no channel echo."""
    w.handle_wzhelp_msg("SomeNick", "host@example.com", "somehandle")
    assert putserv_mock.call_count == len(w.HELP_LINES)
    for call in putserv_mock.call_args_list:
        assert call[0][0].startswith("PRIVMSG SomeNick :")
    # None of the calls should be the "help sent via PM" channel echo
    for call in putserv_mock.call_args_list:
        assert "help sent via PM" not in call[0][0]


# Binds: each weather command routes to its expected handler.


@pytest.mark.parametrize(
    "kind,command,handler_name",
    [
        ("pub", ".w", "handle_wz"),
        ("pub", ".wz", "handle_wz"),
        ("pub", ".wzset", "handle_wzset"),
        ("pub", ".wzhelp", "handle_wzhelp"),
        ("msg", ".w", "handle_wz_msg"),
        ("msg", ".wz", "handle_wz_msg"),
        ("msg", ".wzset", "handle_wzset_msg"),
        ("msg", ".wzhelp", "handle_wzhelp_msg"),
        ("msg", "w", "handle_wz_msg"),
        ("msg", "wz", "handle_wz_msg"),
        ("msg", "wzset", "handle_wzset_msg"),
        ("msg", "wzhelp", "handle_wzhelp_msg"),
    ],
)
def test_bind_registered(kind, command, handler_name):
    """Each (kind, command) tuple is bound to the named handler — not just any handler."""
    expected = (kind, "*", command, getattr(w, handler_name))
    assert expected in [call[0] for call in _bind.call_args_list]
