# EFNet Moto Fleet

Dockerized deployment infrastructure for EFNet #motorcycles Eggdrop IRC bots.
This repository uses Docker Compose and Ansible to manage bot deployments with their unique service dependencies.

## Repository Structure

```text
efnetmoto-fleet/
├── setup.sh                    # Bootstrap script for fresh hosts
├── templates/                  # Shared configuration templates
│   ├── eggdrop.conf.j2
│   └── ...
├── bots/                       # Bot-specific configurations
│   ├── Pompone/
│   ├── Decisis/
│   └── XeroKewl/
├── services/                   # Shared service Dockerfiles
│   ├── pisg/
│   ├── nginx/
│   └── ...
├── shared/                     # Common TCL scripts
│   └── tcl-scripts/
├── ansible/                    # Ansible configuration
│   ├── group_vars/
│   │   └── all.yml
│   ├── host_vars/
│   │   └── localhost/
│   │       ├── overrides.yml   # Local overrides for bot-specific variables
│   │       ├── pompone.yml
│   │       └── xerokewl.yml
│   ├── tasks/                  # Common tasks used in bot-specific playbooks
│   │   ├── deploy-prepare.yml
│   │   ├── deploy-finalize.yml
│   │   ├── backup-prepare.yml
│   │   ├── backup-finalize.yml
│   │   └── ...
│   └── requirements.yml        # Collections and roles installed by ansible-galaxy
└── deploy-*.yml                # Ansible playbooks
```

### Bot Directories

Each bot has its own directory under `bots/` containing:

- `docker-compose.yml` - Defines the bot and any dependent services
- `data/` - Runtime data (userfiles, channel files, generated config)
- `logs/` - Log files (bot and/or channel logs)
- `scripts/` - Bot-specific TCL scripts
- `text/` - Text files (motd, banner, etc.)

### Templates Directory

The `templates/` directory contains shared Jinja2 templates:

- `eggdrop.conf.j2` - Master eggdrop configuration template used by all bots

Ansible renders these templates with bot-specific variables and writes the final configs to each bot's `data/` directory.

### Services Directory

The `services/` directory contains Dockerfiles for all services used across bots:

- `pisg/` - IRC log analyzer (used by Pompone)
- `nginx/` - Custom nginx service to resolve UID mismatch between eggdrop/pisg/nginx containers
- Additional services as needed

Each bot's `docker-compose.yml` references these service definitions via build context.

## Prerequisites

- Linux host
- Git installed
- sudo privileges

## Quick Start

For complete deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

**Brief overview for experienced admins:**

```bash
# 1. Initial setup
git clone git@github.com:efnetmoto/efnetmoto-fleet.git
cd efnetmoto-fleet
./setup.sh

# 2. Configure (optional - review ansible/host_vars/localhost/<botname>.yml)
cp ansible/host_vars/localhost/overrides.yml.example ansible/host_vars/localhost/overrides.yml
# Edit overrides.yml with your changes

# 3. Deploy
ansible-playbook deploy-<botname>.yml --ask-become-pass

# 4. Post-deployment
# - Configure firewall (ports shown in deployment output)
# - Submit PR with SSH Public Keys for offsite backups
# - Link to botnet (see section below)
# - Test backups
```

### Botnet Linking

If adding a new bot to the network, link it via DCC chat:

**On an existing bot:**
```
.+bot <newbotname> <address>:<port>
.chattr <newbotname> +hp
.+host <newbotname> <hostname-or-ip>
.link <newbotname>
```

**On the new bot:**
```
.link <existingbot>
```

**Verify:**
```
.bots        # Shows all linked bots
.whom *      # Shows users across all bots
```

### Bot-Specific Notes

### Decisis

- Includes the `seen` database, tracking which irc nicks have been seen online in the channel.

### Pompone

- Includes pisg (IRC log analyzer) for [stats](https://stats.efnetmoto.com/)
- Generates HTML stats every hour
- Generated stats output available in `bots/Pompone/html/`
- Uses separate log directories (bot/ and channels/) for pisg processing

## Management

> **Note:** Docker Compose commands should be run from the bot's directory to ensure `docker-compose.override.yml` files are automatically loaded for local customizations.

### Check Bot Status

```bash
cd bots/<botname>
docker compose ps
```

### View Logs

```bash
cd bots/<botname>
docker compose logs -f
```

### Restart a Bot

```bash
cd bots/<botname>
docker compose restart
```

### Stop a Bot

```bash
cd bots/<botname>
docker compose down
```

### Update a Bot

```bash
git pull
ansible-playbook deploy-${botname}.yml
```

## Troubleshooting

### First Run Expectations

On first deployment, the bot will start but may not connect to IRC successfully until configured:

1. **Missing Userfile**: If this is a fresh deployment (not migrated from an existing bot),
the bot will warn about a missing userfile in the logs.
This is normal. The bot will create a new userfile on first successful connection.

2. **Owner Not Set**: Without an existing userfile, the bot has no owner.
After first connection, you'll need to DCC chat to the bot and use `.+user handle hostmask`
and `.chattr handle +n` to set an owner.

3. **Channel Files**: On first run, channel files may not exist. The bot will create them when it joins channels.

**Recommended First Run Steps:**

```bash
# Start the bot
# Ansible needs privilege escalation, so we have it ask for our sudo password
ansible-playbook --ask-become-pass deploy-<botname>.yml

# Watch the logs
cd bots/<botname>
docker compose logs -f <botname>

# Once connected to IRC, DCC chat to the bot and set yourself as owner
# Then save the bot's configuration
```

### Stats Not Generating (Pompone)

**Check pisg container:**

```bash
cd bots/Pompone
docker compose logs -f pisg
```

**Common Issues:**

- **No channel logs**: Bot must have `logfile` flags set for the channel (e.g., `jpco` flags)
- **Wrong log directory**: Verify `logs/channels/` exists and has log files
- **PISG config errors**: Check `bots/Pompone/pisg-config/pisg.cfg` for syntax errors
- **Cron schedule**: Default is `@hourly`. Check `CRON_SCHEDULE` env var or wait longer.

**Manual stats generation:**

```bash
cd bots/Pompone
docker compose exec pisg pisg -co /config/pisg.cfg
```

### Port Conflicts

If you see "port already in use" errors:

1. **Check what's using the port:**

   ```bash
   sudo lsof -i :<port>
   ```

2. **Change the port** in `ansible/host_vars/localhost/${botname}.yml`:

   ```yaml
   environment_variables:
     dcc_port: 2021  # Change from default 2020
     stats_port: 8081  # Change from default 8080
   ```

3. **Redeploy:**

   ```bash
   ansible-playbook --ask-become-pass deploy-${botname}.yml
   ```

### Customizations Not Applied

If changes to `ansible/host_vars/localhost/${botname}.yml` aren't taking effect:

1. **Redeploy** to regenerate configs:

   ```bash
   ansible-playbook --ask-become-pass deploy-${botname}.yml
   ```

   This regenerates all auto-generated files including `.env` and `eggdrop.conf`.

2. **Restart containers** to pick up changes:

   ```bash
   cd bots/<botname>
   docker compose restart
   ```

3. **Check generated files** to verify changes:
   - `.env` file (auto-generated by Ansible): `cat bots/<botname>/.env`
   - Eggdrop config (auto-generated by Ansible): `cat bots/<botname>/data/eggdrop.conf`
