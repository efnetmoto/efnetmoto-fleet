"""Decisis bseen tests.

Replies go to the channel by PRIVMSG (bs(quiet_chan) is empty). bs(nicksize) is 9,
so lookup nicks must be 9 characters or fewer; longer ones get no reply at all. The
reply lowercases the looked-up nick, so nick assertions use .lower(). A target still
in the channel is answered with "<nick> is right here!", so an event is only visible
for a target that has since left. bs(flood) is a global 4-in-15-seconds counter shared
by every bseen command, so this module stays at three requests.
"""

from __future__ import annotations

from tests.integration.driver.irc import CHANNEL


def _seen(asker, target_nick: str, want: str, timeout: float = 25.0):
    """Ask `!seen <target_nick>` and return Decisis's PRIVMSG-to-channel reply."""
    asker.say(f"!seen {target_nick}")
    return asker.wait_for_reply(
        lambda n, t: n == "Decisis" and want in t,
        timeout=timeout,
        target=CHANNEL,
    )


def test_seen_never_seen(driver):
    with driver() as asker:
        reply = _seen(asker, "ghost", "don't remember seeing")
        assert "ghost" in reply.text.lower()


def test_seen_part(driver):
    # The target parts but stays connected, so its latest event is "parting", not "quitting".
    with driver() as asker, driver(nick="SeenPart", user="seenpart") as target:
        target.part("#motorcycles", "leaving")
        reply = _seen(asker, "SeenPart", "parting")
        assert "seenpart" in reply.text.lower()
        assert "#motorcycles" in reply.text


def test_seen_quit(driver):
    # Connecting and leaving makes bseen log a quit.
    with driver(nick="SeenQuit", user="seenquit"):
        pass
    with driver() as asker:
        reply = _seen(asker, "SeenQuit", "quitting")
        assert "seenquit" in reply.text.lower()
