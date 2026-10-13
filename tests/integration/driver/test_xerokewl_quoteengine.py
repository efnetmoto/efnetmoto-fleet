"""Xerokewl quoteengine tests.

The driver carries +fo on Xerokewl, so ``!addquote`` (+f) and ``!delquote`` (+o)
work. The quotedb is not reset between runs, so tests add a quote with a unique
title and delete it, which keeps them independent of order. Replies lowercase the
title.

``!quotehelp`` runs last and drains its multi-line reply (see conftest) so the bot's
paced output queue is empty for whatever runs next.
"""

from __future__ import annotations

import re
import time

from tests.integration.driver.irc import CHANNEL

BOT = "Xerokewl"
_QUOTE_LINE = re.compile(r"\x02\S+\x02: .+")  # "<bold-title>: <text>"


def _chan(asker, predicate, timeout: float = 25.0):
    return asker.wait_for_reply(predicate, timeout=timeout, target=CHANNEL)


def _addquote(asker, title: str, text: str) -> None:
    asker.say(f"!addquote {title} {text}")
    _chan(asker, lambda n, t: n == BOT and "added" in t and title.lower() in t.lower())


def _delquote(asker, title: str) -> None:
    asker.say(f"!delquote {title}")
    # Tolerant: a re-delete says "Couldn't find quote ...", not "Deleted quote".
    _chan(
        asker,
        lambda n, t: n == BOT and ("Deleted quote" in t or "Couldn't find" in t),
    )


def test_quotestats(driver):
    with driver() as d:
        d.say("!quotestats")
        reply = _chan(d, lambda n, t: n == BOT and "holds" in t and "quotes" in t)
        assert "quotes" in reply.text


def test_addquote_fetch_delete(driver):
    title = f"Eq{int(time.time() * 1000)}"
    text = "the quick brown fox jumps over the lazy dog"
    with driver() as d:
        _addquote(d, title, text)
        d.say(f"!quote {title}")
        reply = _chan(d, lambda n, t: n == BOT and text in t)
        assert text in reply.text
        _delquote(d, title)
        d.say(f"!quote {title}")
        gone = _chan(d, lambda n, t: n == BOT and "Couldn't find" in t)
        assert text not in gone.text


def test_randquote(driver):
    title = f"Rq{int(time.time() * 1000)}"
    text = "sphinx of black quartz judge my vow"
    with driver() as d:
        _addquote(d, title, text)
        # The db may hold leftover quotes, so !randquote returns *some* quote,
        # not necessarily ours; assert the "<bold-title>: <text>" format.
        d.say("!randquote")
        reply = _chan(d, lambda n, t: n == BOT and _QUOTE_LINE.search(t) is not None)
        assert _QUOTE_LINE.search(reply.text)
        _delquote(d, title)


def test_quotehelp(driver):
    with driver() as d:
        d.say("!quotehelp")
        # Help goes to the asker by PRIVMSG, not to the channel.
        reply = d.wait_for_reply(
            lambda n, t: n == BOT and bool(t),
            timeout=15.0,
            target=d.nick,
        )
        assert reply.text
        # Absorb the remaining help lines so the bot's paced output queue is
        # empty for the next test (putserv spaces them ~2s/line).
        d.drain_until_quiet()
