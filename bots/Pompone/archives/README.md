# PISG Archives Directory

This directory contains archived channel logs from previous years.

## Purpose

At the end of each year, channel logs are archived to keep the active log directory manageable and preserve historical data.

## Archive Format

Archives are named: `logs-YYYY.tar.gz`

Each archive contains all channel log files for that year (e.g. `motorcycles.log.YYYYMMDD`)

## Automatic Rotation

The `rotate-pompone-pisg.yml` playbook runs automatically on January 1st at 00:30 via cron job.

The rotation process:

1. Archives all channel logs from the previous year
2. Moves current HTML stats to a year-specific directory
3. Updates footer.txt with links to all archived years
4. Removes archived log files from the active log directory

## Manual Rotation

To manually rotate for a specific year:

```bash
ansible-playbook rotate-pompone-pisg.yml -e archive_year=2023
```

## Restoring from Archives

To extract logs from an archive:

```bash
tar xzf archives/logs-2023.tar.gz -C bots/Pompone/logs/channels/
```

## Important Notes

- Archive files are included in bot backups
- All files in this directory are gitignored except this README
- Archives are compressed with gzip for space efficiency
