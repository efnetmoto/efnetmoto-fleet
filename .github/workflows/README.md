# GitHub Actions CI

This directory contains GitHub Actions workflows for continuous integration.

## Workflows

### CI Pipeline (ci.yml)

Runs on pull requests to the `main` branch.

**Jobs:**

1. **yaml-lint** - Validates YAML syntax across all files (uses ansible-actions/yamllint-action)
1. **ansible-lint** - Checks Ansible playbooks and vars for best practices (uses ansible-actions/ansible-lint-action)
1. **ansible-syntax** - Verifies playbook syntax is valid
1. **shellcheck** - Lints shell scripts for common issues
1. **hadolint** - Validates Dockerfiles follow best practices
1. **markdown-lint** - Checks markdown formatting
1. **tclint** - Check TCL formatting
1. **secrets-scan** - Scans for accidentally committed secrets

### Go Tests (go-tests.yml)

Runs on pull requests that touch `services/url-shortener/**`. A separate
workflow from `ci.yml` because the Go toolchain is isolated to the
`url-shortener` service.

**Steps:** gofmt check, `go vet`, `staticcheck`, `go test -race`.

### TCL Tests (tcl-tests.yml)

Runs on pull requests that touch `shared/tcl-scripts/**`. Runs the `tcltest`
suite inside an `alpine:3.23` container so tests execute against Tcl 8.6.17
(the version inside the eggdrop image), not dev's Tcl 9.x.

**Steps:** `tclsh tests/all.tcl` (tcltest, single-process-per-file isolation).

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

# TCLint
tclfmt --check .
tclint .

# TCL tests (joingate) — run against the runtime Tcl 8.6
docker run --rm -v "$PWD/shared/tcl-scripts":/t -w /t alpine:3.23 \
  sh -c 'apk add --no-cache tcl >/dev/null && tclsh tests/all.tcl'

# Go tests + lint (url-shortener)
cd services/url-shortener && go test -race ./... && gofmt -l . && go vet ./... && staticcheck ./...
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

# TCLint
pip install tclint

# Go (url-shortener) — Go 1.25+
# Install from https://go.dev/dl/, then:
go install honnef.co/go/tools/cmd/staticcheck@latest
```

## Skipping CI

CI only runs on pull requests to main. Direct pushes to other branches will not trigger CI.

To skip CI on a pull request commit (use sparingly):

```bash
git commit -m "docs: update README [skip ci]"
```
