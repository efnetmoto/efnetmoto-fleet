# GitHub Actions CI

This directory contains GitHub Actions workflows for continuous integration.

## Workflows

### CI Pipeline (ci.yml)

Runs on pull requests to the `main` branch.

**Jobs:**

1. **yaml-lint** - Validates YAML syntax across all files (uses ansible-actions/yamllint-action)
2. **ansible-lint** - Checks Ansible playbooks and vars for best practices (uses ansible-actions/ansible-lint-action)
3. **ansible-syntax** - Verifies playbook syntax is valid
4. **shellcheck** - Lints shell scripts for common issues
5. **hadolint** - Validates Dockerfiles follow best practices
6. **markdown-lint** - Checks markdown formatting
9. **secrets-scan** - Scans for accidentally committed secrets

## Linter Configurations

- `.yamllint.yml` - YAML linting rules
- `.ansible-lint` - Ansible-specific linting rules
- `.markdownlint.yml` - Markdown formatting rules
- `.hadolint.yaml` - Dockerfile linting rules

## Running Locally

To run the same checks locally before pushing:

```bash
# YAML lint
yamllint .

# Ansible lint (targets ansible directory and playbooks)
ansible-lint ansible/ deploy-*.yml

# Ansible syntax check
ansible-playbook --syntax-check deploy-pompone.yml

# ShellCheck
shellcheck setup.sh services/*/entrypoint.sh

# Hadolint
hadolint services/*/Dockerfile

# Markdownlint
markdownlint '**/*.md'
```

## Installing Local Tools

```bash
# Ubuntu/Debian
sudo apt-get install yamllint shellcheck

# Python tools
pip install ansible ansible-lint

# Hadolint
wget -O /usr/local/bin/hadolint https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64
chmod +x /usr/local/bin/hadolint

# Markdownlint (via npm)
npm install -g markdownlint-cli
```

## Skipping CI

CI only runs on pull requests to main. Direct pushes to other branches will not trigger CI.

To skip CI on a pull request commit (use sparingly):

```bash
git commit -m "docs: update README [skip ci]"
```