# Pompone Bot Logs

This directory contains operational logs for the Pompone eggdrop bot.

## Log Files

- `Pompone.log` - Main bot log (mco flags: misc, commands, errors)

## Log Flags

The main bot log captures:
- `m` - Private messages, notices, and CTCPs to the bot
- `c` - Commands executed
- `o` - Misc info, errors, and important events

## Important Notes

- All log files in this directory are gitignored except this README
- Logs are rotated based on config settings (logfile-suffix, switch-logfiles-at)
- These logs are for bot operations only, not channel activity
