# Deploy playbook tests

These tests run the real `deploy-pompone.yml`, `deploy-decisis.yml` and
`deploy-xerokewl.yml` on a disposable GitHub Actions runner and check what they
did to the host. They cover the path a new botmaster follows: checkout, run the
playbook, get correct files and host state, and be able to run it again safely.
Whether a bot actually runs is covered by `tests/integration/`.

`run.sh` runs each playbook twice in a row, then runs `test_deploy.py`, which
checks:

- `eggdrop.conf` renders with the bot's nick, pidfile, channels, servers and
  script list, and no leftover template syntax
- `.env` is mode 0600 and holds exactly the expected variables
- runtime directories, PISG files, and the backup and rotation cron entries exist
- the backup keypair is generated and recorded in `backup_ssh_keys.yml`, and
  peers' keys are installed in `authorized_keys` with the SFTP restriction
- each playbook asks Compose to start its bot project, and the project validates
- the second run changes nothing except the two templates that embed a
  timestamp (`eggdrop.conf`, `pisg.cfg`)

## What is replaced

- `community.docker.docker_compose_v2` is shadowed by a stub in
  `stub-collections/` that records the call instead of starting a bot.
- `vault.yml` is overwritten with dummy plaintext values, and `manage_docker`
  is turned off.

## Running it

CI only. The playbooks write `~/.ssh` keys, crontab entries and
`authorized_keys`, and the script overwrites the vault file, so `run.sh` refuses
to run unless `GITHUB_ACTIONS=true`.

Each bot is run on its own, twice in a row, with `backup_ssh_keys.yml` reset
before it. In production each bot has its own host, so interleaving them on one
runner would test something that never happens.

## Assumptions

The playbooks assume the admin already has SSH configured, meaning a `~/.ssh`
directory exists. `run.sh` creates it to match, since a fresh runner may not
have one.
