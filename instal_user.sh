#!/usr/bin/env bash
set -euo pipefail

#------------------------------------------------------------------------------
# Script paths
#------------------------------------------------------------------------------

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
PROJECT_ROOT="$(dirname "$SCRIPT_PATH")"

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
# Main
#------------------------------------------------------------------------------

if [[ "${EUID}" -eq 0 ]]; then
    echo "Error: this script must not be run as root."
    echo "Run it as your normal user account."
    exit 1
fi

configure_project
