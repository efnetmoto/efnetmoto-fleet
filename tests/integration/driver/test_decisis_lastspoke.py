"""Decisis !lastspoke tests.

!lastspoke reports the last channel message (or /me) from a nick, tracked from the
messages themselves rather than from Eggdrop's idle counter, which restarts whenever
the member record is recreated (a long netsplit, a bot rejoin). A nick that is in the
channel but has not spoken since tracking began gets "no record". The shared bseen
flood counter (4 requests per 15 seconds) is cleared once per module, and this module
stays at three requests.

The netsplit half of the fix (bs_splt/bs_unsplit keeping the pre-split seen record) is
not covered here: the test ircd is a single server, so a split cannot be produced.
"""

from __future__ import annotations

import time

import pytest

from tests.integration.driver.irc import CHANNEL


@pytest.fixture(scope="module", autouse=True)
def _clear_bseen_flood_window():
    time.sleep(16)


def _lastspoke(asker, target_nick: str, want: str, timeout: float = 25.0):
    asker.say(f"!lastspoke {target_nick}")
    return asker.wait_for_reply(
        lambda n, t: n == "Decisis" and want in t,
        timeout=timeout,
        target=CHANNEL,
    )


def _speak(asker, speaker, nick: str, text: str, wire: str | None = None) -> None:
    """Have `speaker` say `text`, returning once `asker` has seen it delivered.

    The two connections are not ordered relative to each other, so without this the
    asker's `!lastspoke` can reach the bots before the speaker's message does.
    """
    speaker.say(wire or text)
    asker.wait_for_reply(lambda n, t: n == nick and text in t, timeout=10, target=CHANNEL)


def test_lastspoke_after_speaking(driver):
    with driver() as asker, driver(nick="SpokeSay", user="spokesay") as target:
        _speak(asker, target, "SpokeSay", "hello from spokesay")
        reply = _lastspoke(asker, "SpokeSay", "last uttered a word")
        assert "spokesay" in reply.text.lower()
        assert "#motorcycles" in reply.text


def test_lastspoke_join_without_speaking_has_no_record(driver):
    # A join must not count as speaking, nor may "since I joined" be reported.
    with driver() as asker, driver(nick="SpokeMute", user="spokemute"):
        reply = _lastspoke(asker, "SpokeMute", "no record of")
        assert "spokemute" in reply.text.lower()


def test_lastspoke_counts_action(driver):
    with driver() as asker, driver(nick="SpokeAct", user="spokeact") as target:
        _speak(asker, target, "SpokeAct", "waves", wire="\x01ACTION waves\x01")
        reply = _lastspoke(asker, "SpokeAct", "last uttered a word")
        assert "spokeact" in reply.text.lower()
