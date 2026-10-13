"""Minimal raw-socket IRC client for the integration driver (zero dependencies).

Connects to the test ircd, registers the test-driver identity, joins
#motorcycles, and exposes send/collect helpers. Runs on the runner against the
ircd's published port — 127.0.0.1:6667 in CI; override INTEGRATION_IRC_HOST/PORT when
the Docker daemon is remote.

The driver's nick/user are coupled to the userfile fixture hostmask
(*!kickstand@*), so eggdrop recognizes it as the registered test user.
"""

from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass, field
from typing import Self

CHANNEL = "#motorcycles"
NICK = os.environ.get("INTEGRATION_DRIVER_NICK", "Kickstand")
USER = os.environ.get("INTEGRATION_DRIVER_USER", "kickstand")
REALNAME = os.environ.get("INTEGRATION_DRIVER_REALNAME", "integration test driver")

CRLF = b"\r\n"


@dataclass
class Message:
    """A parsed IRC line: prefix, command, args (trailing arg is last)."""

    prefix: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    trailing: str = ""

    @property
    def sender_nick(self) -> str:
        return self.prefix.split("!", 1)[0] if "!" in self.prefix else self.prefix

    @property
    def text(self) -> str:
        """The message text for PRIVMSG/NOTICE (the trailing arg)."""
        return self.trailing


def parse(line: str) -> Message:
    prefix = ""
    if line.startswith(":"):
        prefix, _, line = line[1:].partition(" ")
    cmd, _, rest = line.partition(" ")
    args: list[str] = []
    trailing = ""
    while rest:
        if rest.startswith(":"):
            trailing = rest[1:]
            break
        tok, _, rest = rest.partition(" ")
        args.append(tok)
    return Message(prefix=prefix, command=cmd, args=args, trailing=trailing)


class IrcClient:
    """A single IRC connection used by one test."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        timeout: float = 30,
        nick: str | None = None,
        user: str | None = None,
        realname: str | None = None,
    ):
        self.nick = nick or NICK
        self.user = user or USER
        self.realname = realname or REALNAME
        self.host = host or os.environ.get("INTEGRATION_IRC_HOST", "127.0.0.1")
        self.port = int(port or os.environ.get("INTEGRATION_IRC_PORT", "6667"))
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self.sock.settimeout(0.25)
        self._buf = b""
        self._register()
        self._wait_for_code("001", timeout)
        self._send(f"JOIN {CHANNEL}")
        self._wait_for(lambda m: m.command == "JOIN" and m.sender_nick == self.nick, timeout)

    def _send(self, line: str) -> None:
        self.sock.sendall(line.encode() + CRLF)

    def _register(self) -> None:
        self._send(f"NICK {self.nick}")
        self._send(f"USER {self.user} 0 * :{self.realname}")

    def _recv(self) -> list[Message]:
        out: list[Message] = []
        self._buf += self.sock.recv(4096)
        while CRLF in self._buf:
            raw, self._buf = self._buf.split(CRLF, 1)
            if not raw:
                continue
            msg = parse(raw.decode(errors="replace"))
            if msg.command == "PING":
                self._send(f"PONG {msg.trailing or msg.args[0]}")
                continue
            out.append(msg)
        return out

    def _drain(self, deadline: float) -> list[Message]:
        out: list[Message] = []
        while time.time() < deadline:
            try:
                msgs = self._recv()
            except TimeoutError:
                msgs = []
            out.extend(msgs)
            if msgs:
                continue
        return out

    def _wait_for(self, pred, timeout: float = 30) -> Message:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msgs = self._recv()
            except socket.timeout:
                continue
            for m in msgs:
                if pred(m):
                    return m
        raise TimeoutError(f"no message matched within {timeout}s")

    def _wait_for_code(self, code: str, timeout: float = 30) -> None:
        self._wait_for(lambda m: m.command == code, timeout)

    def say(self, text: str, target: str = CHANNEL) -> None:
        self._send(f"PRIVMSG {target} :{text}")

    def privmsg(self, target: str, text: str) -> None:
        self._send(f"PRIVMSG {target} :{text}")

    def join(self, channel: str) -> None:
        self._send(f"JOIN {channel}")

    def part(self, channel: str, reason: str = "") -> None:
        self._send(f"PART {channel} :{reason}")

    def quit(self, reason: str = "done") -> None:
        try:
            self._send(f"QUIT :{reason}")
        except OSError:
            pass
        self.sock.close()

    def collect(self, timeout: float = 3.0) -> list[Message]:
        """Collect PRIVMSG/NOTICE lines for `timeout` seconds."""
        out: list[Message] = []
        for m in self._drain(time.time() + timeout):
            if m.command in ("PRIVMSG", "NOTICE"):
                out.append(m)
        return out

    def drain_until_quiet(self, quiet: float = 3.0, max_wait: float = 35.0) -> float:
        """Absorb incoming traffic until `quiet` seconds pass with none.

        Multi-line bot replies (e.g. ``.wzhelp``) are sent via ``putserv`` at
        eggdrop's paced output rate (~2s/line). If a test matches only the first
        line and disconnects, the bot keeps flushing the rest to the now-gone
        nick and its single-threaded output queue stays busy long enough to
        push the *next* test's reply past its timeout. Draining the full reply
        before disconnect empties the queue, so the following test replies
        promptly. Returns elapsed seconds.
        """
        start = time.time()
        last = time.time()
        while time.time() - start < max_wait and time.time() - last < quiet:
            try:
                msgs = self._recv()
            except TimeoutError:
                msgs = []
            if msgs:
                last = time.time()
        return time.time() - start

    def wait_for_reply(self, predicate, timeout: float = 5.0, target: str | None = None) -> Message:
        """Wait for a PRIVMSG/NOTICE matching predicate(from_nick, text).

        Args:
            predicate: fn(nick, text) -> bool.
            target: if set, only consider messages to this target (channel/driver).
        """

        def want(m: Message) -> bool:
            if m.command not in ("PRIVMSG", "NOTICE"):
                return False
            if target is not None and (not m.args or m.args[0] != target):
                return False
            return predicate(m.sender_nick, m.text)

        return self._wait_for(want, timeout)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.quit()
