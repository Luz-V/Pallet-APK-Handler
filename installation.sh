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
        adb \
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


    # Try current user sudo first
    if command -v sudo >/dev/null 2>&1; then

        if sudo -v; then
            echo "Using sudo privileges..."
            exec sudo -E bash "$SCRIPT_PATH" --root
        fi

        echo "Current user cannot use sudo."
    fi


    # Ask for another administrative account

    echo
    echo "A privileged account is required."
    echo

    read -rp "Administrator account name: " ADMIN_USER

    if [[ -z "$ADMIN_USER" ]]; then
        echo "No administrator account provided."
        exit 1
    fi


    if ! id "$ADMIN_USER" >/dev/null 2>&1; then
        echo "Account '$ADMIN_USER' does not exist."
        exit 1
    fi


    # Root account

    if [[ "$(id -u "$ADMIN_USER")" == "0" ]]; then

        echo "Using root account '$ADMIN_USER'."

        cmd=$(printf 'cd %q && bash %q --root' "$PROJECT_ROOT" "$SCRIPT_PATH")

        exec su - "$ADMIN_USER" -s /bin/bash -c "$cmd"
    fi


    # Sudo-capable account

    if command -v sudo >/dev/null 2>&1 && sudo -l -U "$ADMIN_USER" >/dev/null 2>&1; then

        echo "Using sudo-capable account '$ADMIN_USER'."

        exec su - "$ADMIN_USER" -s /bin/bash -c \
            "cd $(printf '%q' "$PROJECT_ROOT") && sudo bash $(printf '%q' "$SCRIPT_PATH") --root"
    fi


    echo "Account '$ADMIN_USER' cannot provide administrator privileges."
    exit 1
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
