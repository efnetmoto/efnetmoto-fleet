# Integration tests: bots on a test IRC server

These tests start the real bots, point them at a throwaway IRC server, and
drive them over IRC the way a person would. They replace "restart the bot in
production and poke it" as the way to check a change.

Only things this repo controls are real. The IRC server is a local ngircd, the
external APIs (Brave, WeatherAPI, aviationweather.gov) are replaced by a stub
serving the fixtures the unit tests already use, and the url-shortener runs for
real. No test makes a live network call or needs a secret, so the suite runs on
fork PRs.

Because the IRC server and the APIs are stand-ins, a pass here does not show that
EFnet servers, TLS, live API keys or a real host's network will work. It shows
that the bots, scripts, config templates and wiring in this repo work together.

## What runs

| Piece | Where | Notes |
| --- | --- | --- |
| Bots (Pompone, Xerokewl, Decisis) | real `services/eggdrop` image, real `shared/` scripts, config rendered from the real templates | started with each bot's own `docker compose` |
| url-shortener | Pompone's compose | real service, ephemeral SQLite |
| `ircd` | `tests/integration/ircd` | ngircd, no SSL, no oper |
| `api-stub` | `tests/integration/api-stub` | routes listed in its README |
| Driver | `tests/integration/driver` | pytest plus a small raw-socket IRC client |

Everything shares one Docker network, `integration`. The bots link to each other over
it using the peers recorded in `fixtures/*.user`.

## How a run works

`.github/workflows/integration.yml` is the only supported entry point:

1. `scripts/generate-integration-config.py` writes the two override files the repo
   already gitignores: `ansible/host_vars/localhost/overrides.yml` (test IRC
   server, dummy secrets, provider URLs pointing at the stub) and a
   `docker-compose.override.yml` per bot (join the `integration` network, use the
   pre-built images).
2. `render.yml` renders `eggdrop.conf` and `.env` with the real templates and
   vars. It does not touch cron, SSH keys or Docker, and does not need the vault.
3. The userfile fixtures are copied into each bot's `data/`.
4. Images are built with layer caching, `ircd` and `api-stub` start, then each
   bot starts with `docker compose up --no-build`.
5. `pytest tests/integration/driver` waits for all three bots to join `#motorcycles`,
   then runs the tests.

The Eggdrop compile is cached between runs, so only the first run after a
Dockerfile change is slow.

## Running it yourself

There is no supported local runner. The suite needs a Docker daemon that can
bind-mount the checkout, which rules out a remote `DOCKER_HOST`. If you do run
the workflow's steps by hand, point the driver at the server with
`INTEGRATION_IRC_HOST` and `INTEGRATION_IRC_PORT` (defaults `127.0.0.1:6667`).

## Adding a test

Add a plain pytest function to the file for the bot, using the `driver`
fixture. Each connection gets its own nick, because Eggdrop paces replies per
nick and a reused nick inherits the previous test's queued lines.

- **New command on a script:** add a test next to the existing ones and assert
  on the reply.
- **New external provider or endpoint:** add the fixture JSON, add a route in
  `api-stub/server.py`, and add the provider's URL variable to
  `PROVIDER_URL_OVERRIDES` in `scripts/generate-integration-config.py`.
- **A command that needs a flag or a different user:** the userfile fixtures
  must change. See `fixtures/README.md`.

Gotchas that already cost time:

- bseen has a global flood limit of 4 requests per 15 seconds, shared by every
  command. Keep bseen tests to three requests.
- bseen only answers for nicks of 9 characters or fewer.
- The search bot caches results per query in memory, so a query that ran while
  a dependency was down keeps returning the cached fallback until the bot restarts.

## What is not covered

Kick handling (`bots_broke.tcl`, bseen's kick logging), permission-denied paths
for unflagged users, the DCC `searchcache` command, the aprs.fi and Ambient
providers, and PISG. The bots do link, but no test asserts it.
