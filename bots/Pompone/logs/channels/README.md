# Pompone Channel Logs

This directory contains channel activity logs that are processed by pisg for statistics generation.

## Log Files

- `motorcycles.log` - #motorcycles channel activity

## Log Flags

Channel logs capture:

- `j` - Joins, parts, quits, and netsplits
- `k` - Kicks, bans, and mode changes
- `p` - Public text on the channel

## Processing

These logs are consumed by the pisg service to generate HTML statistics. The pisg container mounts this directory as read-only.

## Important Notes

- All log files in this directory are gitignored except this README
- Logs are rotated based on config settings (logfile-suffix, switch-logfiles-at)
- Do not manually modify these logs as it may affect statistics generation
