# eggdrop Service

Custom eggdrop container based on `eggdrop:1.10` with UID adjusted to match other fleet services.

## Purpose

Runs the Eggdrop IRC bot. This is the canonical base image for all bots in the fleet. The container
runs with UID 100 to maintain consistency with other fleet services and to preserve file access
permissions on existing runtime data on disk.

## UID/GID Configuration

- **UID**: 100 (remapped from upstream 1.10's UID 3333)
- **GID**: eggdrop group (inherited from base image)

All bot runtime data (userfiles, channel files, logs) on disk is owned by UID 100. Remapping
preserves that without requiring a chown of existing data across the fleet.

## Implementation

Uses `usermod` from Alpine's `shadow` package to change the existing eggdrop user's UID to 100,
then removes the shadow package to keep image size minimal. This approach:

- Preserves all upstream eggdrop user configuration
- Only modifies the UID that needs changing
- GID is intentionally left as-is; shared volume access is UID-based only

## Usage in docker-compose.yml
```yaml
botname:
  build:
    context: ../../services/eggdrop
    dockerfile: Dockerfile
  stdin_open: true
  volumes:
    - ./data:/home/eggdrop/eggdrop/data
    - ./logs:/home/eggdrop/eggdrop/logs
```

## Base Image

Uses official `eggdrop:1.10` as the base. All default configuration, entrypoint, and command
are inherited unchanged.

## Exposed Ports

Eggdrop does not expose ports at the image level. Ports are configured via environment variables
in each bot's `.env` file and mapped in `docker-compose.yml`.
