#!/usr/bin/env bash
# Run the real deploy-<bot>.yml playbooks twice on a disposable CI runner, then
# check what they did to the host (tests/deploy/test_deploy.py).
#
# The playbooks write ~/.ssh keys, crontab entries and authorized_keys, and this
# script overwrites the vault file, so it only runs on a throwaway GitHub
# runner. Docker is never started: community.docker is shadowed by a stub that
# records the compose call (see stub-collections/).
set -euo pipefail

if [ "${GITHUB_ACTIONS:-}" != "true" ]; then
  echo "refusing to run: this modifies ~/.ssh, crontab and the vault file." >&2
  echo "It is meant for a disposable GitHub Actions runner." >&2
  exit 1
fi

cd "$(dirname "$0")/../.."
out="$PWD/tests/deploy/out"
rm -rf "$out"
mkdir -p "$out"

# The playbooks assume the admin already has SSH set up (a ~/.ssh directory), as
# any host someone logs into over SSH does. Provide that precondition here.
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

cat > ansible/group_vars/vault.yml <<'YAML'
---
vault_aprsfi_key: deploy-test-aprsfi
vault_weatherapi_key: deploy-test-weatherapi
vault_shortener_api_key: deploy-test-shortener
vault_brave_api_key: deploy-test-brave
YAML

cat > ansible/host_vars/localhost/overrides.yml <<'YAML'
---
manage_docker: false
YAML

export ANSIBLE_COLLECTIONS_PATH="$PWD/tests/deploy/stub-collections:$HOME/.ansible/collections"
export ANSIBLE_STDOUT_CALLBACK=ansible.posix.json
export DEPLOY_TEST_COMPOSE_LOG="$out/compose-calls.jsonl"

# Each bot runs twice in a row. All three share this host's single backup
# keypair (in production every bot has its own host), and each bot sets its own
# key comment, so interleaving the bots would make every second run rewrite it.
#
# Every real host starts from the committed backup_ssh_keys.yml, so restore it
# before each bot. Otherwise a later bot would see the test key recorded for the
# earlier ones, and authorized_keys entries that share a key would collide.
for bot in pompone decisis xerokewl; do
  git checkout -- ansible/group_vars/backup_ssh_keys.yml
  for pass in 1 2; do
    echo "== pass $pass: deploy-$bot.yml"
    rc=0
    ansible-playbook "deploy-$bot.yml" > "$out/$bot-pass$pass.json" || rc=$?
    if [ "$rc" -ne 0 ]; then
      echo "deploy-$bot.yml failed (pass $pass); failed tasks:" >&2
      python3 - "$out/$bot-pass$pass.json" <<'PY' >&2 || true
import json, sys
data = json.load(open(sys.argv[1]))
for play in data["plays"]:
    for task in play["tasks"]:
        for host, res in task["hosts"].items():
            if res.get("failed"):
                print(f'- {task["task"]["name"]}: {res.get("msg", res)}')
PY
      exit "$rc"
    fi
  done
  cp ansible/group_vars/backup_ssh_keys.yml "$out/backup_ssh_keys-$bot.yml"
done

python3 -m pytest tests/deploy -v
