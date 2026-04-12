# eggdrop Service

Custom eggdrop container built from source.

## Overview

Eggdrop is built from source rather than using the upstream Docker image. This allows the
container to run unprivileged and takes advantage of multi-stage builds to keep the runtime
image lean. The image includes a Python virtual environment managed by `uv` for use by
Python-based bot scripts.

## Build

Multi-stage build: the builder stage compiles eggdrop against Python and TCL, the runtime stage
copies only the compiled installation and its runtime dependencies.

Source is verified against the eggheads GPG key before building.

## User/Group Configuration

The entrypoint starts as root, chowns `/eggdrop` to the target user, then re-execs as that
user via `su-exec`. The target UID and GID are passed as `EGGDROP_UID` and `EGGDROP_GID`
environment variables, written to each bot's `.env` by Ansible from `ansible_user_uid` and
`ansible_user_gid`.

## Volumes

- `/eggdrop/data` - Persistent bot data (userfile, chanfile, config)
- `/eggdrop/logs` - Bot and channel logs
- `/eggdrop/scripts-shared` - Shared TCL scripts (from repo root)
- `/eggdrop/scripts-python-shared` - Python scripts

## Python Environment

A virtual environment is created at `/eggdrop/.venv` during image build. Dependencies are
installed from `shared/python-scripts/pyproject.toml` via `uv sync --frozen --no-dev`.

To add or update Python dependencies, update `shared/python-scripts/pyproject.toml` and
`uv.lock`, then rebuild the image.

## Build Arguments

- `EGGDROP_VERSION` - Eggdrop version to build (default: `1.10.1`)

## Usage in docker-compose.yml
```yaml
pompone:
  build:
    context: ../..
    dockerfile: services/eggdrop/Dockerfile
  container_name: pompone
  restart: unless-stopped
  stdin_open: true
  ports:
    - "${DCC_PORT}:2020"
    - "${DCC_PORTRANGE}:${DCC_PORTRANGE}"
  volumes:
    - ./data:/eggdrop/data
    - ./logs:/eggdrop/logs
    - ../../shared/tcl-scripts:/eggdrop/scripts-shared
  environment:
    - TZ=${TZ}
    - EGGDROP_UID=${UID}
    - EGGDROP_GID=${GID}
  cap_drop:
    - ALL
  cap_add:
    - CHOWN    # entrypoint chown -R /eggdrop before privilege drop
    - SETUID   # su-exec setuid() to drop to EGGDROP_UID
    - SETGID   # su-exec setgid() to drop to EGGDROP_GID
  mem_limit: 64m
  memswap_limit: 64m
  cpus: 0.10
  security_opt:
    - no-new-privileges:true
  healthcheck:
    test: ["CMD", "nc", "-z", "127.0.0.1", "2020"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 60s  # allow time for chown, script load, DCC port bind
```

## Exposed Ports

Eggdrop does not expose ports at the image level. Ports are configured via environment variables
in each bot's `.env` file and mapped in `docker-compose.yml`.
