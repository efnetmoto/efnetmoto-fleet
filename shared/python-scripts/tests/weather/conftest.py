import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from weather.models import LocationResult, LocationType

# Installed at module level — conftest is always imported before any test file,
# so weather.prefs and weather.py see this mock when they do from-imports of eggdrop.
eggdrop_mock = MagicMock()
sys.modules["eggdrop"] = eggdrop_mock
sys.modules["eggdrop.tcl"] = eggdrop_mock.tcl

# Must be set before providers are instantiated at module level in
# test_weather_handlers.py (which calls exec_module during import).
os.environ.setdefault("WEATHERAPI_KEY", "test-key")
os.environ.setdefault("APRSFI_KEY", "test-key")


@pytest.fixture
def eggdrop_mock():
    return sys.modules["eggdrop"]


@pytest.fixture(scope="session")
def fixtures_dir():
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def ksfo_loc():
    return LocationResult(type=LocationType.ICAO, query="KSFO", raw="KSFO")
