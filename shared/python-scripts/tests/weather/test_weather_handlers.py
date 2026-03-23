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
_eggdrop_mock.bind = _bind
_eggdrop_mock.tcl.putserv = _putserv
_eggdrop_mock.tcl.putlog = _putlog

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
