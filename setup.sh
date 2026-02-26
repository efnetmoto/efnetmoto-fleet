#!/bin/bash
# Bootstrap script for eggdrop-fleet deployment
# This script prepares a fresh host for Ansible-based bot deployment

set -e

echo "=========================================="
echo "EFNet #motorcycles Eggdrop Fleet Bootstrap"
echo "=========================================="
echo

# Check for sudo privileges
echo "[1/4] Checking for sudo privileges..."
if ! sudo -v; then
    echo "ERROR: This script requires sudo privileges."
    echo "Please run again and enter your password when prompted."
    exit 1
fi
echo "✓ Sudo access confirmed"
echo

# Detect OS
echo "[2/4] Detecting operating system..."
if [ -f /etc/os-release ]; then
    # This file is expected to exist on Linux hosts but not all dev environments
    # shellcheck disable=SC1091
    . /etc/os-release
    OS=$ID
    echo "✓ Detected: $PRETTY_NAME"
else
    echo "ERROR: Cannot detect operating system"
    exit 1
fi
echo

echo "[3/4] Checking for Ansible..."
if command -v ansible-playbook > /dev/null 2>&1; then
    ANSIBLE_VERSION=$(ansible --version | head -n1)
    echo "✓ Ansible already installed: $ANSIBLE_VERSION"
else
    echo "Ansible not found. Installing..."
    case $OS in
        ubuntu)
            echo "Installing Ansible via apt (PPA)..."
            sudo apt-get update
            sudo apt-get install -y software-properties-common
            sudo apt-add-repository --yes --update ppa:ansible/ansible
            sudo apt-get update
            sudo apt-get install -y ansible
            ;;
        debian)
            echo "Installing Ansible via apt (Ansible PPA)..."
            case $VERSION_ID in
                11) UBUNTU_CODENAME=focal ;;
                12) UBUNTU_CODENAME=jammy ;;
                *)
                    echo "ERROR: Unsupported Debian version: $VERSION_ID"
                    echo "Please install Ansible manually: https://docs.ansible.com/ansible/latest/installation_guide/"
                    exit 1
                    ;;
            esac
            sudo apt-get update
            sudo apt-get install -y wget gnupg
            wget -O- "https://keyserver.ubuntu.com/pks/lookup?fingerprint=on&op=get&search=0x6125E2A8C77F2818FB7BD15B93C4A3FD7BB9C367" \
                | sudo gpg --dearmor -o /usr/share/keyrings/ansible-archive-keyring.gpg
            echo "deb [signed-by=/usr/share/keyrings/ansible-archive-keyring.gpg] http://ppa.launchpad.net/ansible/ansible/ubuntu ${UBUNTU_CODENAME} main" \
                | sudo tee /etc/apt/sources.list.d/ansible.list
            sudo apt-get update
            sudo apt-get install -y ansible
            ;;
        centos|rhel|fedora)
            echo "Installing Ansible via dnf/yum..."
            if command -v dnf > /dev/null 2>&1; then
                sudo dnf install -y ansible
            else
                sudo yum install -y ansible
            fi
            ;;
        *)
            echo "ERROR: Unsupported OS: $OS"
            echo "Please install Ansible manually: https://docs.ansible.com/ansible/latest/installation_guide/"
            exit 1
            ;;
    esac

    # Verify Ansible installation
    if ! command -v ansible-playbook > /dev/null 2>&1; then
        echo "ERROR: Ansible installation failed"
        exit 1
    fi

    ANSIBLE_VERSION=$(ansible --version | head -n1)
    echo "✓ Ansible installed: $ANSIBLE_VERSION"
fi
echo

# Install required Ansible collections
echo "[4/4] Checking Ansible collections..."
REQUIREMENTS_FILE="ansible/requirements.yml"

if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "WARNING: $REQUIREMENTS_FILE not found"
    echo "Skipping collection & roles installation"
else
    echo "Installing/updating Ansible collections from $REQUIREMENTS_FILE..."
    ansible-galaxy collection install -r "$REQUIREMENTS_FILE"
    echo "✓ Collections installed"
    echo "Installing/updating Ansible roles from $REQUIREMENTS_FILE..."
    ansible-galaxy role install -r "$REQUIREMENTS_FILE"
    echo "✓ Roles installed"
fi


echo
echo "======================================"
echo "Bootstrap Complete!"
echo "======================================"
echo
echo "Next steps:"
echo "  1. Review and customize bot variables in ansible/host_vars/localhost/"
echo "  2. Deploy a bot:"
echo "       ansible-playbook deploy-botname.yml --ask-become-pass"
echo
