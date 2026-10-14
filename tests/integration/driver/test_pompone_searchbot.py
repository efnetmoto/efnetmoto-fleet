"""Pompone searchbot tests.

The url-shortener runs for real, so the short URL in a reply is genuine. The words
``one`` and ``zero`` in a query choose which fixture the api-stub returns. Each test
uses its own nick so the per-nick search cooldown (5s by default) doesn't make
adjacent tests interfere. ``!g`` is bound for any user, so the nick needn't be
registered.
"""

from __future__ import annotations

import re

from tests.integration.driver.irc import CHANNEL

BOT = "Pompone"
_SHORT_URL = re.compile(r"go\.efnetmoto\.com/\S+")


def test_g_one_result_yields_short_url(driver):
    with driver(nick="Apex1", user="apex") as d:
        d.say("!g show me one result")
        reply = d.wait_for_reply(
            lambda n, t: n == BOT and _SHORT_URL.search(t) is not None,
            timeout=25.0,
            target=CHANNEL,
        )
        assert _SHORT_URL.search(reply.text)


def test_g_zero_results_says_no_results(driver):
    with driver(nick="Apex2", user="apex") as d:
        d.say("!g show me zero results")
        reply = d.wait_for_reply(
            lambda n, t: n == BOT and "No results found" in t,
            timeout=25.0,
            target=CHANNEL,
        )
        assert "No results found" in reply.text
