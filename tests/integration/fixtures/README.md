# Userfile fixtures

`decisis.user`, `pompone.user` and `xerokewl.user` are Eggdrop userfiles that
the integration suite copies into `bots/<Bot>/data/<Bot>.user` before the bots start.
They give the test run three things without any partyline scripting:

- **Botnet links.** Each bot has the other two as peers (`<service>:2020`,
  link password `e2elink`), so they link on boot.
- **An owner** (`botboss`) so the partyline is reachable when debugging.
- **One registered test user**, `Kickstand`, matched by the hostmask
  `*!kickstand@*` / `*!?kickstand@*`. On Xerokewl it carries `+fo`, which is
  what `!addquote` (`f`) and `!delquote` (`o`) require. `.wzset` only needs the
  user to be registered. The driver connects with the ident `kickstand`
  (`tests/integration/driver/irc.py`), so the two must stay in agreement.

## Why they are committed, not generated per run

A fresh Eggdrop with `learn-users 0` and no userfile has no account to log in
with, so the partyline commands that create peers and users cannot be scripted
from a clean boot. Password hashes are also minted by Eggdrop itself (pbkdf2),
so hand-writing the file is brittle. Eggdrop writes the file once; we commit it.

## When to regenerate

- You need another test user or different flags (for example an unflagged user
  for permission-denied tests).
- A bot is added, removed or renamed, or its listen port changes.
- An Eggdrop upgrade changes the userfile format.

## How to regenerate

Needs a Docker daemon that can bind-mount this checkout (a remote daemon cannot
see your local files). Run from the repo root.

1. Render in bootstrap mode, with no existing userfiles:

   ```bash
   rm -f bots/*/data/*.user
   python3 tests/integration/scripts/generate-integration-config.py --bootstrap
   ansible-playbook tests/integration/render.yml
   ```

   `--bootstrap` makes the bots start as `eggdrop -ntm`, which mints an owner
   from the first `/msg <bot> hello`.

2. Build and start the stack, using the same steps as
   `.github/workflows/integration.yml` (build the four images, create the `integration` network,
   start `ircd` and `api-stub`, then `docker compose up -d --no-build` for each
   bot).

3. Drive the one-time setup from a container on the `integration` network:

   ```bash
   docker run --network integration --rm \
     -v "$PWD/tests/integration/scripts/bootstrap-userfiles.py:/x.py:ro" \
     docker.io/library/python:3.12-alpine python3 /x.py
   ```

   It creates the owner on each bot, adds the other two bots as peers, adds
   `Kickstand`, and runs `.save`. Edit the constants at the top of the script
   to change users, flags or peers.

4. Switch back to normal mode and confirm the bots link on their own:

   ```bash
   python3 tests/integration/scripts/generate-integration-config.py
   for b in Pompone Xerokewl Decisis; do
     (cd bots/$b && docker compose up -d --no-build --force-recreate)
   done
   ```

   Telnet to a bot's partyline as `botboss` (password `e2elink`) and run
   `.bots`; all three should be listed without you issuing `.link`.

5. Copy the files out and review the diff:

   ```bash
   for b in Pompone Xerokewl Decisis; do
     cp "bots/$b/data/$b.user" "tests/integration/fixtures/$(echo $b | tr A-Z a-z).user"
   done
   git diff --stat tests/integration/fixtures
   ```

The files hold only test credentials and container addresses. Nothing here is
a real secret.
