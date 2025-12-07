#!/bin/sh
set -e

# Check for required config file
if [ ! -f "/config/pisg.cfg" ]; then
    echo "ERROR: /config/pisg.cfg not found!"
    echo "Please mount a pisg configuration file to /config/pisg.cfg"
    exit 1
fi

# Run pisg once on startup, if configured, to generate initial stats
if [ "${STATSGEN_ON_STARTUP}" = "true" ]; then
    echo "Running pisg initial generation..."
    pisg -co /config/pisg.cfg
fi

# If the script has any arguments, invoke the CLI instead
if [ "$#" -gt 0 ]; then
    pisg "$@"
else
# Otherwise, start with cron
    echo "Starting cron schedule using: ${CRON_SCHEDULE}"
    echo "${CRON_SCHEDULE} /pisg/pisg -co /config/pisg.cfg" > /tmp/crontab
    supercronic -passthrough-logs /tmp/crontab
fi
