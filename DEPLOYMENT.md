# Deployment Guide for Bot Administrators

This guide walks through the complete process of deploying a bot from scratch, including SSH key setup for off-site backups.

## Overview

Each bot in the efnetmoto-fleet operates independently on its own host, managed by a bot administrator. The bots form a resilient network where:
- **Pompone** logs all channel activity and hosts PISG statistics
- **Decisis** hosts the IRC seen database
- **XeroKewl** hosts the quote database
- All bots share userfiles via the botnet
- All bots back up to all other bots for redundancy

## Prerequisites

- Linux host (Debian and Redhat currently supported)
- sudo access
- Git installed
- (Optional) Existing bot backup for migration

## Step 1: Clone Repository

```bash
git clone https://github.com/efnetmoto/efnetmoto-fleet.git
cd efnetmoto-fleet
```

## Step 2: Run Bootstrap Script

The setup script installs Ansible and required dependencies:

```bash
chmod +x setup.sh
./setup.sh
```

## Step 3: Configure Bot Variables

View your bot's variable file (`ansible/host_vars/localhost/<botname>.yml`):

```yaml
# Bot Identity
bot_nick: "<nick>"
bot_username: "<username>"
bot_realname: "<realname>"
bot_admin: "<Your Name> <email@example.com>"
bot_owner: "<YourIRCHandle>"

# Ports
dcc_port: 2020
stats_port: 8080  # Only for Pompone
```

If you wish to change any of these for your local installation, use the overrides file:

```bash
cp ansible/host_vars/localhost/override.yml.example ansible/host_vars/localhost/override.yml
vi ansible/host_vars/localhost/override.yml
```

## Step 4: Migrate Existing Bot Data (Optional)

If migrating an existing bot, obtain a recent backup from another bot admin and restore from backup:

```bash
# Copy backup to repository
mv ~/<botname>-backup-YYYY-MM-DD.tar.gz efnetmoto-fleet/backups/

# Restore the backup and redeploy
ansible-playbook restore-<botname>.yml --ask-become-pass
ansible-playbook deploy-<botname>.yml --ask-become-pass

# Restart services to pick up restored data
cd bots/<botname>
docker compose restart
```

## Step 5: Deploy Your Bot

Run the deployment playbook:

```bash
ansible-playbook deploy-<botname>.yml --ask-become-pass
```

The playbook will:
- Install Docker (if needed)
- Generate SSH backup keypair automatically
- Update `ansible/group_vars/backup_ssh_keys.yml` with connection details
- Generate bot configuration from templates
- Set up SSH authorized_keys for other bots (using keys from repository)
- Build and start containers
- Install backup cron jobs

**Important:** The deployment will display a message if SSH keys were generated or updated. You must commit these changes and submit a PR (see Step 8 below).

## Step 6: Verify Deployment

> **Note:** Run Docker Compose commands from the bot's directory to ensure `docker-compose.override.yml` files are automatically loaded for local customizations.

Check that services are running:

```bash
cd bots/<botname>
docker compose ps
```

View logs:

```bash
cd bots/<botname>
docker compose logs -f
```

Verify the bot joined IRC and check for any errors.

## Step 7: Test Backup System

Run a manual backup:

```bash
ansible-playbook backup-<botname>.yml
```

Verify the backup was created:

```bash
ls -lh backups/
```

The backup will attempt to copy to other bots. If their deployment hasn't been updated with your keys yet, you'll see failures. This is expected - once your PR is merged and they redeploy, backups will succeed.

## Step 8: Commit Your Changes

Create a pull request with your changes:

```bash
git checkout -b add-<botname>-deployment
git add ansible/group_vars/backup_ssh_keys.yml
git add ansible/host_vars/localhost/<botname>.yml
git commit -m "Add <botname> deployment configuration

- Add bot configuration in host_vars
- Auto-generated SSH backup keys and connection details"
git push origin add-<botname>-deployment
```

**Important:** Once your PR is merged, other bot administrators must pull the latest changes and redeploy to authorize your bot to push backups to them:

```bash
git pull origin main
ansible-playbook deploy-<theirbotname>.yml --ask-become-pass
```

## Ongoing Maintenance

### Backups

#### Automated Backups

Backups run automatically via cron daily (configured during deployment). Check logs:

```bash
cat /var/log/backup-<botname>.log
```

#### Manual Backup

Run the backup playbook for any bot:

```bash
ansible-playbook backup-<botname>.yml
```

This creates a timestamped backup file:

```text
backups/<botname>-backup-2023-12-08.tar.gz
```

#### Backup Retention

Backups older than 30 days (configurable) are automatically deleted when a new backup is created.

To change retention period, edit `backup_retention_days` in your bot's variables file.

#### Restoring from Backup

Backups are restored using a structured restore pipeline that validates the archive and restored contents before cleanup. This helps prevent accidental or partial restores.

**Basic Restore Command:**

```bash
ansible-playbook -K restore-<botname>.yml --extra-vars "archive_file=backups/<botname>-backup-2023-12-08.tar.gz"
```

> 📝 **Note:** `-K` (become root) needed to work around file permissions on bot-owned files

**Archive Validation:**

The restore pipeline validates that:
- Archive filename matches expected format: `<botname>-backup-YYYY-MM-DD.tar.gz`
- Bot name in filename matches the target bot
- Archive MIME type indicates gzip compression
- Required directories (`data/`, `logs/`) were restored
- Optional artifacts are restored only if they existed in the backup

If validation fails, the restore process stops immediately and the staging directory is preserved for inspection.

**Testing Restores:**

Test your restore procedure periodically to ensure backups are valid!

### Updating Configuration

1. Edit variables in `ansible/host_vars/localhost/<botname>.yml` or `ansible/host_vars/localhost/overrides.yml`
2. Redeploy: `ansible-playbook deploy-<botname>.yml --ask-become-pass`

### Rotating SSH Keys

If you need to rotate your backup SSH key:

1. Delete old key: `rm ~/.ssh/efnetmoto_backup*`
2. Redeploy: `ansible-playbook deploy-<botname>.yml --ask-become-pass`
3. Deployment will auto-generate new keys and update `ansible/group_vars/backup_ssh_keys.yml`
4. Commit changes and create PR with new keys
5. Wait for other admins to pull and redeploy to authorize your new key

## Disaster Recovery

This section covers recovering from a complete bot host failure.

### Scenario: Bot Host Failure

If a bot's host becomes unavailable or needs to be rebuilt:

**Step 1: Obtain a Backup**

Contact another bot administrator via IRC to obtain a recent backup file.

**Step 2: Set Up New Host**

Follow the standard deployment procedure (Steps 1-8 in this guide):
- Clone repository
- Run bootstrap script
- Configure bot variables
- Deploy the bot

The deployment will automatically generate NEW SSH backup keys (old private key is lost) and update `ansible/group_vars/backup_ssh_keys.yml` with your new connection details (user, host, path, ssh_public_key).

**Step 3: Restore from Backup**

```bash
# Copy backup to repository
mv ~/<botname>-backup-YYYY-MM-DD.tar.gz efnetmoto-fleet/backups/

# Restore the backup and redeploy
ansible-playbook restore-<botname>.yml --ask-become-pass
ansible-playbook deploy-<botname>.yml --ask-become-pass

# Restart services to pick up restored data
cd bots/<botname>
docker compose restart
```

**Step 4: Update SSH Keys in Repository**

The deployment automatically updated `ansible/group_vars/backup_ssh_keys.yml` with your new SSH public key and connection details. Create a PR with this change:

```bash
git checkout -b update-<botname>-recovery
git add ansible/group_vars/backup_ssh_keys.yml
git commit -m "Update <botname> SSH keys and connection details after recovery"
git push origin update-<botname>-recovery
```

**Step 5: Coordinate with Other Admins**

Once your PR is merged, notify other bot administrators to pull and redeploy:

```bash
git pull origin main
ansible-playbook deploy-<theirbotname>.yml --ask-become-pass
```

This will authorize your new SSH key and update your connection details for off-site backups. No manual coordination of hostnames or paths is needed - everything is automatically captured during deployment.

**Step 6: Re-establish Botnet Links**

After restore, verify botnet connectivity. The bots should already know about each other from their restored userfiles.

Check botnet status:
```
.bots        # Shows linked bots
.whom *      # Shows users on all bots
```

If a bot isn't linking automatically, you may need to update its host information:

```
.+host <botname> <new-hostname-or-ip>
.chattr <botname> +h             # Ensure hub flag is set
.link <botname>                  # Manually initiate link
```

**Step 7: Verify Backup System**

Test that your bot can now back up to other bots:

```bash
ansible-playbook backup-<botname>.yml
```

The backup output will show success/failure for each target bot. Once other admins have pulled and redeployed (Step 5), all targets should show SUCCESS.

**Step 8: Post-Recovery Verification**

- [ ] Bot connects to IRC successfully
- [ ] Bot joins all expected channels
- [ ] Botnet links are established (`.bots` shows all bots)
- [ ] Userfile is intact (`.match *` shows users)
- [ ] Bot responds to commands
- [ ] Backups complete successfully
- [ ] Stats generation works (Pompone only)

### Recovery Time Estimate

With backup file in hand and SSH key coordination with other admins:
- Fresh host setup: 15-30 minutes
- Restore and verification: 15-30 minutes
- SSH key coordination: Depends on other admins' availability

### Notes

- **Private keys are lost** in host failure - this is expected and acceptable
- **Botnet linking** should be automatic from restored userfiles in most cases
- **SSH coordination** requires other admins to merge PR and redeploy
- **Backup retrieval** depends on out-of-band communication (IRC) with other admins

## Troubleshooting

### Bot Won't Connect to IRC

Check server configuration:

```bash
grep -A 5 "set servers" bots/<botname>/data/eggdrop.conf
```

Verify network connectivity:

```bash
docker exec <container-name> ping -c 3 irc.example.com
```

### Backup Fails to Copy to Remote Hosts

Check SSH connectivity:

```bash
ssh -i ~/.ssh/efnetmoto_backup user@remote-host
```

Verify authorized_keys on remote host:

```bash
# On remote host
cat ~/.ssh/authorized_keys | grep <your-bot-name>
```

### Permission Errors

Ensure directories have correct ownership:

```bash
ls -la bots/<botname>/data/
```

All files should be owned by UID 100 (container user).

## Security Considerations

- **SSH Keys:** Private keys never leave your host. Only public keys are committed.
- **Backup Files:** Contain sensitive data (user passwords, channel keys). Stored with 0600 permissions.
- **Docker Compose Overrides:** Can contain sensitive configuration. These files are gitignored.
- **Ansible Vault:** Not currently used, but available for highly sensitive data if needed.

## Getting Help

- Review bot-specific README files in `bots/<botname>/`
- Check CONTRIBUTING.md for development guidelines
- Contact other bot administrators via IRC
- Review deployment logs for error messages

## Bot-Specific Notes

### Pompone
- Runs PISG statistics (cron job installed automatically)
- Annual stats rotation on January 1st
- Stats available at https://stats.efnetmoto.com/

### Decisis
- Hosts IRC seen database

### XeroKewl
- Hosts quote database