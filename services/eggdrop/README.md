# eggdrop Service

Custom eggdrop container built from source.

## Overview

Eggdrop is built from source rather than using the upstream Docker image. This allows the
container to run unprivileged and takes advantage of multi-stage builds to keep the runtime
image lean.

## Build

Multi-stage build: the builder stage compiles eggdrop, the runtime stage copies only the
compiled installation and its runtime dependencies.

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
  volumes:
    - ./data:/eggdrop/data
    - ./logs:/eggdrop/logs
    - ../../shared/tcl-scripts:/eggdrop/scripts-shared
  environment:
    - TZ=${TZ}
    - EGGDROP_UID=${UID}
    - EGGDROP_GID=${GID}
```

## Exposed Ports

Eggdrop does not expose ports at the image level. Ports are configured via environment variables
in each bot's `.env` file and mapped in `docker-compose.yml`.
