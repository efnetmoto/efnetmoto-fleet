#!/usr/bin/python
"""Stand-in for community.docker.docker_compose_v2 used by the deploy tests.

The deploy tests check what the playbooks do to a host, not whether Docker can
start a bot (the integration suite covers that). This module records each call to the
JSONL file named by $DEPLOY_TEST_COMPOSE_LOG instead of starting anything, and
always reports "no change" so the idempotence check stays meaningful.

The argument spec is deliberately strict: if a playbook starts passing a new
argument, the test fails and the stub needs to learn about it.
"""

import json
import os

from ansible.module_utils.basic import AnsibleModule


def main():
    module = AnsibleModule(
        argument_spec={
            "project_src": {"type": "str", "required": True},
            "state": {"type": "str", "default": "present"},
        },
        supports_check_mode=True,
    )
    log = os.environ.get("DEPLOY_TEST_COMPOSE_LOG")
    if log and not module.check_mode:
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(module.params, sort_keys=True) + "\n")
    module.exit_json(changed=False)


if __name__ == "__main__":
    main()
