# Shared TCL Scripts

This directory contains 3rd-party TCL Scripts that are used by one or more bots.

## Script Index

| Filename | Description |
| --- | --- |
| `bseen1.4.2.tcl` | Maintains database of seen and lastspoke for all channel users |

## Architecture

Scripts in this directory are automatically mounted into each bot at
`/home/eggdrop/eggdrop/scripts-shared` via a volume specified in `docker-compose.yml`.
However, each bot's configuration needs to be edited to tell it to load the script.  This
is done via the bot-specific ansible variables in `host_vars/`.

## Usage

1. Copy the TCL Script to this directory.
1. For each bot that should load the script, add the path to the bot's variables

   ```yaml
   bot_scripts:
     - "scripts/alltools.tcl"
     - "scripts-shared/newscript.tcl"  <-- this is the new script
   ```

1. Restart the bot(s)

   ```bash
   cd bots/<botname>
   docker compose restart
   ```
