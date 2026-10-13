"""Xerokewl weather tests.

WeatherAPI and AvWx are served by the api-stub. ``.wzset`` requires a registered
user, which the driver is. ``.wzhelp`` runs last and drains its multi-line reply (see
conftest) so the bot's paced output queue is empty for whatever runs next. Timeouts
are generous (25s) to tolerate brief bot stalls, such as a botnet link's reverse-DNS
timeout blocking eggdrop's loop.
"""

from __future__ import annotations

from tests.integration.driver.irc import CHANNEL

BOT = "Xerokewl"


def test_wz_weatherapi_current(driver):
    with driver() as d:
        d.say(".wz 94025")
        # "San Francisco" comes from the weatherapi_current fixture.
        reply = d.wait_for_reply(
            lambda n, t: n == BOT and "San Francisco" in t,
            timeout=25.0,
            target=CHANNEL,
        )
        assert "San Francisco" in reply.text


def test_wz_metar(driver):
    with driver() as d:
        d.say(".wz --metar KSFO")
        # "KSFO" comes from the avwx_metar fixture.
        reply = d.wait_for_reply(
            lambda n, t: n == BOT and "KSFO" in t,
            timeout=25.0,
            target=CHANNEL,
        )
        assert "KSFO" in reply.text


def test_wzset_registered_then_uses_default(driver):
    with driver() as d:
        d.say(".wzset 94025")
        d.wait_for_reply(
            lambda n, t: n == BOT and "Default set to" in t,
            timeout=25.0,
            target=CHANNEL,
        )
        # With no argument, .wz uses the saved default.
        d.say(".wz")
        reply = d.wait_for_reply(
            lambda n, t: n == BOT and "San Francisco" in t,
            timeout=25.0,
            target=CHANNEL,
        )
        assert "San Francisco" in reply.text


def test_wzhelp(driver):
    with driver() as d:
        d.say(".wzhelp")
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
