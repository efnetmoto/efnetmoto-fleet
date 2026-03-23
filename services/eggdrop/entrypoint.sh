#!/bin/ash
# shellcheck shell=dash
set -e

# Start as root to fix /eggdrop ownership, then drop to the runtime user.
if [ "$(id -u)" = "0" ]; then
    TARGET_UID="${EGGDROP_UID:?EGGDROP_UID environment variable must be set}"
    TARGET_GID="${EGGDROP_GID:?EGGDROP_GID environment variable must be set}"
    chown -R "${TARGET_UID}:${TARGET_GID}" /eggdrop
    exec su-exec "${TARGET_UID}:${TARGET_GID}" "$0" "$@"
fi

CONFIG=data/eggdrop.conf

# Activate Python virtualenv
# shellcheck source=/dev/null
. /eggdrop/.venv/bin/activate

# Remove stale PID file if present
PID=$(grep "set pidfile" ${CONFIG})
case "$PID" in
  \#*)
    PIDNEXT=$(grep "set botnet-nick" ${CONFIG})
    case "$PIDNEXT" in
      \#*) PIDNEXT=$(grep "set nick" ${CONFIG}) ;;
    esac
    PIDBASE=$(echo $PIDNEXT | awk '{gsub("\"", "", $3); print $3}')
    PID="pid.$PIDBASE"
    ;;
  *)
    PID=$(echo $PID | awk '{gsub("\"", "", $3); print $3}')
    ;;
esac
if [ -e "$PID" ]; then
  echo "Found $PID, removing..."
  rm "$PID"
fi

exec ./eggdrop -nt ${CONFIG}
