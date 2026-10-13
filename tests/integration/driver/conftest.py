"""Shared fixtures for the integration driver tests.

Each connection uses a unique nick; the USER stays ``kickstand``, which is what
matches the userfile hostmask. Eggdrop paces multi-line replies (``.wzhelp``,
``!quotehelp``) at ~2s/line, so if a test reused a nick, the previous connection's
leftover help lines would flood the next connection and push its reply past the
timeout.
"""

from __future__ import annotations

import os
import secrets
import time

import pytest

from tests.integration.driver.irc import CHANNEL, USER, IrcClient

BOT_NICKS = {"Pompone", "Xerokewl", "Decisis"}
_BOTS_JOINED_TIMEOUT = float(os.environ.get("INTEGRATION_BOTS_JOINED_TIMEOUT", "90"))


def _unique_nick() -> str:
    """A unique nick of 9 characters, the longest bseen will look up.

    The random suffix avoids colliding with ghost nicks from earlier runs.
    """
    return f"Rider{secrets.token_hex(2)}"


def _names_present(client: IrcClient) -> set[str]:
    """Trigger a NAMES reply and return the current channel members."""
    client._send(f"NAMES {CHANNEL}")
    deadline = time.time() + 5
    while time.time() < deadline:
        for m in client._drain(min(time.time() + 0.5, deadline)):
            # RPL_NAMREPLY: args=[nick, '=', '#chan'] trailing=names
            if m.command == "353":
                return {n.lstrip("@+%~&") for n in m.trailing.split()}
    return set()


@pytest.fixture(scope="session")
def bots_joined() -> None:
    """Wait until all 3 bots have joined #motorcycles (connectivity gate)."""
    probe = IrcClient(nick=_unique_nick(), user="probe")
    try:
        deadline = time.time() + _BOTS_JOINED_TIMEOUT
        while time.time() < deadline:
            if BOT_NICKS.issubset(_names_present(probe)):  # type: ignore[attr-defined]
                return
            time.sleep(2)
        raise TimeoutError(
            f"bots {BOT_NICKS} did not join {CHANNEL} within {_BOTS_JOINED_TIMEOUT}s"
        )
    finally:
        probe.quit()


@pytest.fixture
def driver(bots_joined):
    """A fresh registered test-driver connection (per test, so bseen sees join).

    Each call gets a unique nick (USER stays ``kickstand`` for the hostmask
    match); pass ``nick=`` to use a specific nick (e.g. a bseen target)."""

    def _make(nick: str | None = None, user: str = USER) -> IrcClient:
        return IrcClient(nick=nick or _unique_nick(), user=user)

    return _make
