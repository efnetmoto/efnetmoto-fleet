#!/usr/bin/env python3
"""Generate the userfile fixtures for the integration tests.

Run after the bots are up in ``--bootstrap`` mode. For each bot it creates the owner,
adds the other two bots as botnet peers, adds the test driver user, and saves. It
runs inside a container on the integration network; the full procedure is in
fixtures/README.md. Stdlib only.
"""

from __future__ import annotations

import socket
import sys
import time

IRC_HOST = "ircd"
IRC_PORT = 6667

OWNER_NICK = "botboss"  # IRC nick for /msg hello -> owner handle (<=9 chars)
OWNER_PASS = "e2elink"  # partyline login password AND botnet link password

# (bot nick, docker-DNS service name). Peer handle = bot nick; userfile = <nick>.user.
BOTS = [("Decisis", "decisis"), ("Xerokewl", "xerokewl"), ("Pompone", "pompone")]

DRIVER_HANDLE = "Kickstand"  # matched by the hostmasks below, not by the nick
# ngircd runs with Ident = no, so it prefixes the USER with '~'; '?' matches that
# optional tilde. The plain form is also added for an ircd that doesn't add one.
DRIVER_HOSTMASKS = ["*!kickstand@*", "*!?kickstand@*"]
# Flags for the test driver: +fo on Xerokewl (quoteengine add/del); just registered elsewhere.
DRIVER_PLUSFO_BOTS = {"Xerokewl"}


class Irc:
    """Minimal IRC client for the hello/pass phase."""

    def __init__(self, nick: str):
        self.sock = socket.create_connection((IRC_HOST, IRC_PORT), timeout=10)
        self.sock.settimeout(0.5)
        self._buf = b""
        self._send(f"NICK {nick}")
        self._send(f"USER {nick.lower()} 0 * :integration fixture bootstrap")
        self._wait_code("001", 10)

    def _send(self, line: str) -> None:
        self.sock.sendall(line.encode() + b"\r\n")

    def _drain(self, deadline: float) -> list[str]:
        out: list[str] = []
        while time.time() < deadline:
            try:
                self._buf += self.sock.recv(4096)
            except socket.timeout:
                pass
            while b"\r\n" in self._buf:
                raw, self._buf = self._buf.split(b"\r\n", 1)
                if raw:
                    out.append(raw.decode(errors="replace"))
        return out

    def _wait_code(self, code: str, timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            for line in self._drain(time.time() + 0.5):
                if line.startswith(":") and f" {code} " in line:
                    return
        raise TimeoutError(f"no IRC {code} within {timeout}s")

    def msg(self, target: str, text: str) -> None:
        self._send(f"PRIVMSG {target} :{text}")

    def collect(self, timeout: float = 2.0) -> list[str]:
        return [ln for ln in self._drain(time.time() + timeout) if ln.startswith(":")]

    def quit(self) -> None:
        try:
            self._send("QUIT :bootstrap")
        except OSError:
            pass
        self.sock.close()


def irc_phase() -> None:
    print("=== IRC phase: /msg hello + pass on each bot ===", flush=True)
    irc = Irc(OWNER_NICK)
    try:
        for nick, _svc in BOTS:
            irc.msg(nick, "hello")
            time.sleep(0.3)
            replies = irc.collect(3.0)
            print(f"  [{nick}] hello -> {len(replies)} reply lines", flush=True)
            for r in replies:
                if nick in r:
                    print(f"    {r}", flush=True)
            irc.msg(nick, f"pass {OWNER_PASS}")
            time.sleep(0.3)
            replies = irc.collect(3.0)
            print(f"  [{nick}] pass  -> {len(replies)} reply lines", flush=True)
            for r in replies:
                if nick in r:
                    print(f"    {r}", flush=True)
    finally:
        irc.quit()
    print("=== IRC phase done ===\n", flush=True)


def partyline(service: str) -> socket.socket:
    """Connect + login to <service>:2020 as the owner; return the socket."""
    s = socket.create_connection((service, 2020), timeout=10)
    s.settimeout(0.6)
    _read(s, 2.0)  # banner / "account name" prompt
    _send(s, OWNER_NICK)
    _read(s, 2.0)  # "password" prompt
    _send(s, OWNER_PASS)
    banner = _read(s, 3.0)
    if "invalid" in banner.lower() or "denied" in banner.lower() or "no such" in banner.lower():
        raise RuntimeError(f"partyline login to {service} rejected: {banner[-200:]!r}")
    return s


def _send(s: socket.socket, line: str) -> None:
    s.sendall((line + "\n").encode())


def _read(s: socket.socket, timeout: float) -> str:
    """Read until `timeout` seconds elapsed with a 0.5s quiet gap."""
    out = b""
    end = time.time() + timeout
    while time.time() < end:
        try:
            chunk = s.recv(4096)
            if not chunk:
                break
            out += chunk
        except socket.timeout:
            if out and time.time() > end - timeout + 0.5:
                break
    return out.decode(errors="replace")


def cmd(s: socket.socket, line: str, settle: float = 1.5) -> str:
    """Send a partyline command, return the response text."""
    _send(s, line)
    return _read(s, settle)


def pcmd(s: socket.socket, label: str, line: str) -> None:
    """Send a partyline command and print a truncated, labeled response."""
    print(f"  {label}", cmd(s, line).strip()[:120], flush=True)


def partyline_phase() -> None:
    print("=== Partyline phase: link peers + add test driver ===", flush=True)
    for nick, svc in BOTS:
        print(f"-- {nick} ({svc}:2020) --", flush=True)
        try:
            s = partyline(svc)
        except (OSError, RuntimeError) as e:
            print(f"  !! {e}", flush=True)
            continue
        try:
            for peer_nick, peer_svc in BOTS:
                if peer_nick == nick:
                    continue
                pcmd(s, ".+bot", f".+bot {peer_nick} {peer_svc}:2020")
                pcmd(s, ".chattr", f".chattr {peer_nick} +hp")
                pcmd(s, ".+host", f".+host {peer_nick} {peer_nick}!*@*")
                pcmd(s, ".chpass", f".chpass {peer_nick} {OWNER_PASS}")
            pcmd(s, ".+user", f".+user {DRIVER_HANDLE} {DRIVER_HOSTMASKS[0]}")
            for hm in DRIVER_HOSTMASKS[1:]:
                pcmd(s, ".+host", f".+host {DRIVER_HANDLE} {hm}")
            if nick in DRIVER_PLUSFO_BOTS:
                pcmd(s, ".chattr +fo", f".chattr {DRIVER_HANDLE} +fo")
            pcmd(s, ".save", ".save")
        finally:
            _send(s, ".quit")
            s.close()
    print("=== Partyline phase done ===\n", flush=True)


def main() -> int:
    irc_phase()
    partyline_phase()
    print("Bootstrap complete. Next steps:", flush=True)
    print("  1. restart bots in NORMAL mode (regenerate overrides without --bootstrap)", flush=True)
    print("  2. confirm auto-link (partyline .bots / .whom *)", flush=True)
    print(
        "  3. snapshot bots/<bot>/data/<Bot>.user -> tests/integration/fixtures/<bot>.user",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
