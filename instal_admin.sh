#!/usr/bin/env bash
set -euo pipefail

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
        p7zip-full \
        libxcb-xinerama0 \
        libxcb-cursor0 \
        libxkbcommon-x11-0 \
        libxcb1 \
        libxcb-render0 \
        libxcb-shape0 \
        libxcb-xfixes0 \
        qt5-gtk-platformtheme

    command -v python3 >/dev/null
    command -v aapt >/dev/null
    command -v 7z >/dev/null

    echo
    echo "System packages successfully installed."
}

#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------

if [[ "${EUID}" -ne 0 ]]; then
    echo "Error: this script must be run as root."
    echo
    echo "Use:"
    echo "  sudo ./install-admin.sh"
    exit 1
fi

install_system_packages
