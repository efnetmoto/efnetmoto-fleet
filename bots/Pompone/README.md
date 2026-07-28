# Pompone

Pompone is the main bot: it runs PISG (hourly stats served at
<https://stats.efnetmoto.com/>) and the `url-shortener` service
(`go.efnetmoto.com`).

## Anti-Troll Join-Gate

Pompone is the **only** bot that runs the join-gate (`scripts-shared/joingate.tcl`).
The gate must run on exactly one bot per channel so two bots never race to voice
the same joiner. Do not enable `joingate.tcl` on Decisis or Xerokewl.

The channel mode `+m` (moderated) that the gate depends on is managed by Ansible
in `ansible/group_vars/all.yml`, not by the plugin. Disabling the gate
(`JOINGATE_ENABLED=0`) stops the voicing logic but leaves `+m` on, so the channel
becomes fully muted — to re-open the channel, also remove `+m` from the Ansible
channel config.

At cutover, run `gatesync` (pub/dcc/msg, `+o` only) once the bot is opped to voice
all current known/allowlisted occupants.
