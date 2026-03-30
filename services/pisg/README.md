# PISG Service

Docker container for pisg (Perl IRC Statistics Generator).

## Overview

This container processes IRC channel logs and generates HTML statistics pages.
It's designed to work with the eggdrop container logs.

## User/Group Configuration

The container runs as whatever user is specified by the Docker Compose `user:` directive,
matching the host user running the fleet. This ensures consistent file permissions across
all services without UID hardcoding in the image.

## Volumes

- `/logs` - Read-only mount of channel logs (from eggdrop)
- `/cache` - Pisg cache directory for faster processing
- `/output` - Generated HTML statistics files
- `/config` - Configuration directory containing pisg.cfg

## Environment Variables

- `CRON_SCHEDULE` - Cron schedule for stats regeneration (default: @hourly)

## Configuration File

The container requires a `pisg.cfg` file mounted at `/config/pisg.cfg`. Example:
```text
<set>
  Logdir = "/logs/"
  OutputFile = "/output/index.html"
  Maintainer = "Your Name <you@example.com>"
  PageHeader = "Channel Statistics"
  
  <channel="#motorcycles">
    Logfile = "/logs/motorcycles.log.*"
    Format = "eggdrop"
  </channel>
</set>
```

## Usage in docker-compose.yml
```yaml
pisg:
  build:
    context: ../../services/pisg
    dockerfile: Dockerfile
  container_name: pompone-pisg
  restart: unless-stopped
  user: "${UID}:${GID}"
  volumes:
    - ./logs/channels:/logs:ro
    - ./pisg-cache:/cache
    - ./html:/output
    - ./config/pisg.cfg:/config/pisg.cfg:ro
  environment:
    - CRON_SCHEDULE="@hourly"
```

## Log File Format

Pisg supports multiple log formats. For eggdrop logs, use `Format = "eggdrop"` in your config.

The logfile path in pisg.cfg can use wildcards to process dated logs:
```text
Logfile = "/logs/motorcycles.log.*"
```

This will process files like:

- `motorcycles.log.20251208`
- `motorcycles.log.20251209`
