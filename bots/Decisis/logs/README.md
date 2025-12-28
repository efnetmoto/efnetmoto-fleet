# Decisis Logs Directory

This directory contains operational logs for the Decisis eggdrop bot.

## Log Files

- `Decisis.log` - Main bot log (mco flags: misc, commands, errors)

## Log Flags

The main bot log captures:

- `m` - Private messages, notices, and CTCPs to the bot
- `c` - Commands executed
- `o` - Misc info, errors, and important events

## Important Notes

- All log files in this directory are gitignored except this README
- Logs are rotated based on config settings (logfile-suffix, switch-logfiles-at)
- Decisis does not log channel activity (only operational logs)
