# Pompone Data Directory

This directory contains persistent runtime data for the Pompone eggdrop bot.

## Files Generated at Runtime

- `eggdrop.conf` - Bot configuration (generated from template by Ansible)
- `Pompone.user` - User database
- `Pompone.chan` - Channel database

## Important Notes

- All files in this directory are gitignored except this README
- These files are generated/managed by the running bot
- For initial deployment, Ansible will populate the config file
- User and channel files will be created on first run or migrated from existing installation
