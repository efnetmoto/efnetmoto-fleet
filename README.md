# Eggdrop Fleet

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
│   └── XeroKewl/
├── services/                   # Shared service Dockerfiles
│   ├── pisg/
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
│   ├── tasks/
│   │   ├── common.yml          # Common tasks uses in bot-specific playbooks
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
- Additional services as needed

Each bot's `docker-compose.yml` references these service definitions via build context.

## Prerequisites

- Linux host
- Git installed
- sudo privileges

## Quick Start

### Initial Setup

On a fresh host, clone the repository and run the setup script:

```bash
git clone <repository-url> eggdrop-fleet
cd eggdrop-fleet
./setup.sh
```

The setup script will install:

- Ansible
- Required Ansible collections

### Configure Bots

For each bot you want to deploy:

1. Review bot-specific variables in `ansible/host_vars/localhost/<botname>.yml`
   and identify any you may wish to change.

2. Edit the overrides file `ansible/host_vars/localhost/overrides.yml` with any
   local overrides you wish to make

### Deploy Bots

Deploy a single bot:

```bash
ansible-playbook deploy-pompone.yml
```

### Bot-Specific Notes

### Pompone

- Includes pisg (IRC log analyzer) for [stats](https://stats.efnetmoto.com/)
- Generates HTML stats every hour
- Generated stats output available in `bots/Pompone/html/`
- Uses separate log directories (bot/ and channels/) for pisg processing

## Management

### Check Bot Status

```bash
docker compose -f bots/<botname>/docker-compose.yml ps
```

### View Logs

```bash
docker compose -f bots/<botname>/docker-compose.yml logs -f
```

### Restart a Bot

```bash
docker compose -f bots/<botname>/docker-compose.yml restart
```

### Stop a Bot

```bash
docker compose -f bots/<botname>/docker-compose.yml down
```

### Update a Bot

```bash
git pull
ansible-playbook deploy-<botname>.yml
```

## Security Notes

- Review firewall rules for IRC ports
- Secrets must use Ansible Vault

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
ansible-playbook deploy-pompone.yml

# Watch the logs
docker compose -f bots/Pompone/docker-compose.yml logs -f pompone

# Once connected to IRC, DCC chat to the bot and set yourself as owner
# Then save the bot's configuration
```

### Bot Won't Connect to IRC

**Check logs:**

```bash
docker compose -f bots/<botname>/docker-compose.yml logs -f
```

**Common Issues:**

- **"Can't resolve server"**: DNS issue or incorrect server in `ansible/group_vars/all.yml`
- **Connection timeout**: Check firewall rules for outbound IRC ports (6667, 7000)
- **"User/host not matched"**: Bot is connecting but not identified. Check userfile and hostmasks.
- **Immediate disconnect**: Server may be banning the bot. Check for clone bots or K-lines.

### Bot Starts Then Exits

**Check for:**

- Syntax errors in eggdrop config: `docker compose -f bots/<botname>/docker-compose.yml logs`
- Missing `stdin_open: true` in docker-compose.yml (bot needs this to stay alive)
- TCL script errors: Check logs for script load failures

### Stats Not Generating (Pompone)

**Check pisg container:**

```bash
docker compose -f bots/Pompone/docker-compose.yml logs -f pisg
```

**Common Issues:**

- **No channel logs**: Bot must have `logfile` flags set for the channel (e.g., `jpco` flags)
- **Wrong log directory**: Verify `logs/channels/` exists and has log files
- **PISG config errors**: Check `bots/Pompone/pisg-config/pisg.cfg` for syntax errors
- **Cron schedule**: Default is `@hourly`. Check `CRON_SCHEDULE` env var or wait longer.

**Manual stats generation:**

```bash
docker compose -f bots/Pompone/docker-compose.yml exec pisg pisg -co /config/pisg.cfg
```

### Port Conflicts

If you see "port already in use" errors:

1. **Check what's using the port:**

   ```bash
   sudo lsof -i :<port>
   ```

2. **Change the port** in `ansible/host_vars/localhost/<botname>.yml`:

   ```yaml
   environment_variables:
     dcc_port: 2021  # Change from default 2020
     stats_port: 8081  # Change from default 8080
   ```

3. **Redeploy:**

   ```bash
   ansible-playbook deploy-<botname>.yml
   ```

### Container Won't Start

**Check container status:**

```bash
docker compose -f bots/<botname>/docker-compose.yml ps -a
```

**View detailed logs:**

```bash
docker compose -f bots/<botname>/docker-compose.yml logs --tail=50
```

**Check for:**

- Volume mount errors (permissions, missing directories)
- Port binding conflicts
- Resource limits (disk space, memory)

### Customizations Not Applied

If changes to `ansible/host_vars/localhost/<botname>.yml` aren't taking effect:

1. **Redeploy** to regenerate configs:

   ```bash
   ansible-playbook deploy-<botname>.yml
   ```

2. **Restart containers** to pick up new .env values:

   ```bash
   docker compose -f bots/<botname>/docker-compose.yml restart
   ```

3. **Check generated files**:
   - `.env` file: `cat bots/<botname>/.env`
   - Eggdrop config: `cat bots/<botname>/data/eggdrop.conf`

### Getting Help

**Collect diagnostic info:**

```bash
# Container status
docker compose -f bots/<botname>/docker-compose.yml ps

# Recent logs
docker compose -f bots/<botname>/docker-compose.yml logs --tail=100

# Check .env file
cat bots/<botname>/.env

# Check generated config
cat bots/<botname>/data/eggdrop.conf
```

Include this information when asking for help or opening issues.
