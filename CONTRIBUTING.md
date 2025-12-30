# Contributing to Eggdrop Fleet

This document provides guidelines for contributing to the efnetmoto-fleet repository,
including repository structure, development workflows, and best practices.

## Bot Directory Structure

Each bot follows this standard structure:

```text
bots/BotName/
├── docker-compose.yml                    # Service definitions
├── docker-compose.override.yml.example   # Local customization overrides
├── data/                                 # Runtime data (gitignored except README)
│   └── README.md
└── logs/                                 # Log files (gitignored except READMEs)
    └── README.md
```

## Development Guidelines

### Adding a New Bot

1. Create bot directory structure:

   ```bash
   mkdir -p bots/NewBot/{data,logs}
   ```

2. Create `docker-compose.yml` based on an existing bot

3. Add bot-specific variables:

   ```bash
   cp ansible/host_vars/localhost/pompone.yml ansible/host_vars/localhost/newbot.yml
   ```

4. Create deployment playbook:

   ```bash
   cp deploy-pompone.yml deploy-newbot.yml
   # Update bot name and paths
   ```

5. Add documentation to README.md

### Adding a New Service

Services are reusable Docker containers that bots can use.

1. Create service directory:

   ```bash
   mkdir -p services/myservice
   ```

2. Create `Dockerfile`:
   - Base on Alpine when possible (matches eggdrop UID/GID)
   - Use `adduser -S servicename` for user creation
   - Document environment variables

3. Create `entrypoint.sh` if needed:
   - Make it executable
   - Use `/bin/sh` shebang for Alpine compatibility
   - Include error handling with `set -e`

4. Create `README.md`:
   - Purpose and overview
   - Volume requirements
   - Environment variables
   - Usage example in docker-compose

5. Reference in bot's `docker-compose.yml`:

   ```yaml
   myservice:
     build:
       context: ../../services/myservice
       dockerfile: Dockerfile
     volumes:
       - ./data:/data
   ```

### Modifying Templates

Templates use Jinja2 syntax and are rendered by Ansible.

**Common variables:**

- `{{ bot_nick }}` - Bot nickname
- `{{ bot_owner }}` - Bot owner handle
- `{{ irc_network }}` - Network name (from group_vars)
- `{{ ansible_default_ipv4.address }}` - Host IP
- `{{ ansible_date_time.tz }}` - System timezone

**Template locations:**

- `templates/eggdrop.conf.j2` - Main bot config
- `templates/pisg.cfg.j2` - Statistics config

**Testing template changes:**

```bash
ansible-playbook deploy-pompone.yml --ask-become-pass --check
```

### Ansible Best Practices

**Variable precedence (lowest to highest):**

1. `ansible/group_vars/all.yml` - Common to all bots
2. `ansible/group_vars/backup_ssh_keys.yml` - SSH Public Key inventory for offsite backups
3. `ansible/host_vars/localhost/botname.yml` - Bot-specific
4. Command line `-e` flags - Overrides

**Use group_vars for:**

- IRC network settings
- Server lists
- Channel definitions
- Common DCC settings

**Use host_vars for:**

- Bot identity (nick, username, realname)
- Bot-specific ports
- Service enables (pisg_enabled)
- Custom scripts list
- Bot-specific overrides (extra_config)

**Playbook structure:**

```yaml
- name: Descriptive playbook name
  hosts: localhost
  connection: local
  
  vars_files:
    - ansible/group_vars/all.yml
    - ansible/group_vars/backup_ssh_keys.yml
    - ansible/host_vars/localhost/botname.yml
  
  tasks:
    - name: Load local override vars if present
      ansible.builtin.include_vars:
        file: ansible/host_vars/localhost/overrides.yml
      when: ansible.builtin.stat(path='ansible/host_vars/localhost/overrides.yml').stat.exists

    - name: Run common tasks
      ansible.builtin.import_tasks: ansible/tasks/deploy-common.yml

   - name: Descriptive task names
```

### Docker Compose Guidelines

**Image selection:**

- Use official images when available (`eggdrop:1.9.5`)
- Pin specific versions, avoid `latest`
- Build custom services from `services/` directory

**Volume mounts:**

- Use read-only (`:ro`) when appropriate
- Document volume purposes in comments

**Networks:**

- Each bot gets its own network
- Services within a bot share the network

**Environment variables:**

- Use for non-sensitive configuration
- Document all variables in comments
- Keep secrets in `.env` files (gitignored)

### Testing Changes

**Before committing:**

1. Test on a clean system or VM
2. Run setup.sh to verify bootstrap
3. Deploy a bot to ensure playbook works
4. Check generated configs are correct
5. Verify services start and operate correctly

**Test commands:**

```bash
# Syntax check playbook
ansible-playbook deploy-pompone.yml --syntax-check

# Dry run
ansible-playbook deploy-pompone.yml --check

# Deploy to test environment
ansible-playbook deploy-pompone.yml --ask-become-pass

# Verify deployment
cd bots/Pompone
docker compose ps
docker compose logs
```

### Git Workflow

**Branch naming:**

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates

**Commit messages:**

- Use present tense ("Add feature" not "Added feature")
- Be descriptive but concise
- Reference issues when applicable

**What to commit:**

- Source files, templates, playbooks
- Documentation and examples
- Static configuration files
- README files in gitignored directories

**What NOT to commit:**

- Runtime data (`.user`, `.chan`, `.notes` files)
- Generated configs (`eggdrop.conf`, `pisg.cfg`)
- Log files
- `.env` files with secrets
- `docker-compose.override.yml` (user-specific)
- Cache directories

### Documentation

**When to update documentation:**

- Adding new features
- Changing configuration options
- Adding new bots or services
- Modifying workflows

**Documentation locations:**

- `README.md` - User-facing, deployment focused
- `CONTRIBUTING.md` - Developer-focused (this file)
- `bots/*/README.md` - Bot-specific details
- `services/*/README.md` - Service documentation
- Inline comments in code

### Code Style

**Shell scripts:**

- Use `#!/bin/bash` for bash, `#!/bin/sh` for POSIX sh
- Include `set -e` for error handling
- Comment complex logic
- Use descriptive variable names

**Ansible:**

- Use YAML anchors for repeated config
- Keep playbooks focused and modular
- Use descriptive task names
- Add comments for non-obvious logic

**Docker:**

- Multi-stage builds when appropriate
- Minimize layers
- Clean up in same RUN command
- Document exposed ports and volumes

## Questions or Issues?

- Review existing code for patterns
- Check documentation in relevant directories
- Test thoroughly before submitting changes
- Ask for clarification if unsure
