# ircd

A pinned, repo-owned **ngircd** image used as the IRC server for the integration
tests. It replaces a live EFnet server so the tests are deterministic and make no
outbound network calls.

## Why our own image

We pin `alpine:3.24` (same digest as the eggdrop image) and `apk add ngircd`
rather than trusting a third-party ngircd image — matching the fleet's ethos of
pinning images we control and not pulling arbitrary images into CI.

## Scope

Covers the IRC event surface the suite exercises: `JOIN`, `PART`, `QUIT`,
`NICK`, `PRIVMSG`, `NOTICE`. There is **no oper block**: nothing under test
kicks, and eggdrop permission checks use their
own userfile flags rather than IRC channel modes, so IRC op is irrelevant here.

If ngircd ever lacks a needed feature, InspIRCd is the obvious replacement.

## Usage in the suite

Built as `efnetmoto/ircd:integration` and run on the shared `integration` bridge
network as container name `ircd`. Bots connect to `ircd:6667` (docker DNS); the pytest
driver connects to `127.0.0.1:6667` (the runner-published port). See
`../README.md` and `.github/workflows/integration.yml`.
