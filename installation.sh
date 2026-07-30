#!/usr/bin/env bash
set -euo pipefail

#------------------------------------------------------------------------------
# Script paths
#------------------------------------------------------------------------------

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
PROJECT_ROOT="$(dirname "$SCRIPT_PATH")"

#------------------------------------------------------------------------------
# Install system packages (root only)
#------------------------------------------------------------------------------

install_system_packages() {

    if [[ ! -f /etc/debian_version ]]; then
        echo "Error: this script only supports Debian-based distributions."
        exit 1
    fi

    export DEBIAN_FRONTEND=noninteractive

    apt-get update

    apt-get install -y \
        python3 \
        python3-venv \
        python3-pip \
        aapt \
        p7zip-full

    command -v python3 >/dev/null
    command -v aapt >/dev/null
    command -v 7z >/dev/null

    echo
    echo "System packages successfully installed."
}

#------------------------------------------------------------------------------
# Configure the Python environment
#------------------------------------------------------------------------------

configure_project() {

    cd "$PROJECT_ROOT"

    if [[ ! -d ".venv" ]]; then
        echo "Creating virtual environment..."
        python3 -m venv .venv
    else
        echo "Virtual environment already exists."
    fi

    source .venv/bin/activate

    python -m pip install --upgrade pip setuptools wheel

    pip install -r requirements.txt

    deactivate

    echo
    echo "Project successfully configured."
    echo
    echo "To activate the environment:"
    echo "source .venv/bin/activate"
}

#------------------------------------------------------------------------------
# Root execution
#------------------------------------------------------------------------------

run_as_root() {

    if [[ "${EUID}" -ne 0 ]]; then
        echo "Error: root privileges are required."
        exit 1
    fi

    install_system_packages
}

#------------------------------------------------------------------------------
# Privilege escalation
#------------------------------------------------------------------------------

ensure_root() {

    if [[ "${EUID}" -eq 0 ]]; then
        return
    fi


    # Try sudo first
    if command -v sudo >/dev/null 2>&1; then

        echo "Root privileges required. Requesting sudo access..."

        sudo -v

        exec sudo -E bash "$SCRIPT_PATH" --root
    fi


    # Fallback to su
    echo
    echo "sudo is not available."
    echo "A root account is required."
    echo

    read -rp "Root account name: " ROOT_USER

    if [[ -z "$ROOT_USER" ]]; then
        echo "No root account provided."
        exit 1
    fi


    uid="$(id -u "$ROOT_USER" 2>/dev/null || true)"

    if [[ "$uid" != "0" ]]; then
        echo "Account '$ROOT_USER' is not a root account."
        exit 1
    fi


    cmd=$(printf 'cd %q && bash %q --root' "$PROJECT_ROOT" "$SCRIPT_PATH")

    exec su - "$ROOT_USER" -s /bin/bash -c "$cmd"
}

#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------

case "${1:-}" in

    --root)

        run_as_root
        configure_project
        ;;


    *)

        ensure_root

        ;;
esac
