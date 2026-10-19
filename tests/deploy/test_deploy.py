"""Checks on what the real deploy-<bot>.yml playbooks did to the host.

tests/deploy/run.sh runs the playbooks and saves their JSON output under
tests/deploy/out/, which these tests read alongside the files left on the host.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests" / "deploy" / "out"
BOTS = ["Pompone", "Decisis", "Xerokewl"]

# These templates embed ansible_date_time (and the server list is shuffled), so
# their tasks report "changed" on every run. Anything else changing on the
# second run is a real idempotence problem.
CHANGES_EVERY_RUN = {
    "Generate eggdrop.conf from template",
    "Generate pisg.cfg from template",
}


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _vars(bot: str) -> dict:
    merged = _yaml(ROOT / "ansible/group_vars/all.yml")
    merged.update(_yaml(ROOT / f"ansible/host_vars/localhost/{bot.lower()}.yml"))
    return merged


def _run(bot: str, n: int) -> dict:
    return json.loads((OUT / f"{bot.lower()}-pass{n}.json").read_text())


def _crontab() -> str:
    return subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=True).stdout


bot_param = pytest.mark.parametrize("bot", BOTS)


@bot_param
def test_conf_rendered(bot):
    v = _vars(bot)
    conf = (ROOT / f"bots/{bot}/data/eggdrop.conf").read_text()

    assert "{{" not in conf and "{%" not in conf
    assert f'set nick "{bot}"' in conf
    assert f'set pidfile "data/pid.{bot}"' in conf
    assert len(re.findall(r"^server add ", conf, re.M)) == len(v["irc_servers"])
    for channel in v["channels"]:
        assert f"channel add {channel['name']} " in conf
    for script in v["bot_scripts"]:
        loader = "pysource" if script.endswith(".py") else "source"
        assert re.search(rf"^{loader} {re.escape(script)}$", conf, re.M), script


@bot_param
def test_env_file(bot):
    env = ROOT / f"bots/{bot}/.env"
    assert env.stat().st_mode & 0o777 == 0o600

    text = env.read_text()
    assert "{{" not in text
    keys = {line.split("=", 1)[0] for line in text.splitlines() if "=" in line}
    expected = {k.upper() for k in _vars(bot)["environment_variables"]} | {"UID", "GID"}
    assert keys == expected


@bot_param
def test_runtime_dirs_created(bot):
    for d in _vars(bot)["runtime_dirs"]:
        assert (ROOT / d).is_dir(), d


@bot_param
def test_daily_backup_cron(bot):
    cron = _crontab()
    assert f"Daily {bot} backup" in cron
    assert f"backup-{bot.lower()}.yml" in cron


def test_pompone_pisg_artifacts():
    for name in ("pisg.cfg", "footer.txt"):
        assert (ROOT / "bots/Pompone/pisg-config" / name).is_file(), name
    assert "Annual stats rotation" in _crontab()


@bot_param
def test_backup_key_recorded(bot):
    ssh = Path.home() / ".ssh"
    private = ssh / "efnetmoto_backup"
    assert private.stat().st_mode & 0o777 == 0o600

    record = _yaml(OUT / f"backup_ssh_keys-{bot.lower()}.yml")["backup_ssh_public_keys"][
        bot.lower()
    ]
    pub = (ssh / "efnetmoto_backup.pub").read_text().split()
    assert record["ssh_public_key"].split()[:2] == pub[:2]
    assert record["path"] == f"{ROOT}/backups"


def test_peer_keys_are_restricted_in_authorized_keys():
    wrapper = ROOT / "shared/bin/backups-sftp-restriction.sh"
    assert wrapper.stat().st_mode & 0o777 == 0o755
    assert f'ALLOWED_DIR="{ROOT}/backups"' in wrapper.read_text()

    lines = [
        line
        for line in (Path.home() / ".ssh/authorized_keys").read_text().splitlines()
        if "efnetmoto backup from" in line
    ]
    assert len(lines) >= 2
    for line in lines:
        assert line.startswith(f'restrict,command="{wrapper}" ssh-ed25519 '), line


@bot_param
def test_compose_started_for_bot(bot):
    calls = [json.loads(line) for line in (OUT / "compose-calls.jsonl").read_text().splitlines()]
    mine = [c for c in calls if c["project_src"] == f"bots/{bot}"]
    assert mine and all(c["state"] == "present" for c in mine)


@bot_param
def test_second_run_changes_nothing_unexpected(bot):
    first, second = _run(bot, 1), _run(bot, 2)
    assert first["stats"]["localhost"]["failures"] == 0
    assert second["stats"]["localhost"]["failures"] == 0

    changed = {
        task["task"]["name"]
        for play in second["plays"]
        for task in play["tasks"]
        if any(res.get("changed") for res in task["hosts"].values())
    }
    assert changed <= CHANGES_EVERY_RUN, changed - CHANGES_EVERY_RUN


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
@bot_param
def test_rendered_compose_project_is_valid(bot):
    result = subprocess.run(
        ["docker", "compose", "config", "-q"],
        cwd=ROOT / "bots" / bot,
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    assert result.returncode == 0, result.stderr
