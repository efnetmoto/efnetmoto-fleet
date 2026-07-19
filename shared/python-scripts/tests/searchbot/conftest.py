import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Install the eggdrop mock at module level so any `from eggdrop import bind`
# or `from eggdrop.tcl import putlog, putserv, putdcc` resolves to a mock.
# Must happen before searchbot.py is loaded by the handler tests.
eggdrop_mock = MagicMock()
sys.modules["eggdrop"] = eggdrop_mock
sys.modules["eggdrop.tcl"] = eggdrop_mock.tcl

# searchbot.py reads required env vars at import time; set defaults before any
# module-level instantiation.
os.environ.setdefault("BRAVE_API_KEY", "test-brave-key")
os.environ.setdefault("SHORTENER_API_URL", "http://url-shortener:8080")
os.environ.setdefault("SHORTENER_API_KEY", "test-shortener-key")


@pytest.fixture
def eggdrop_mock():
    return sys.modules["eggdrop"]


@pytest.fixture(scope="session")
def fixtures_dir():
    return Path(__file__).parent / "fixtures"
