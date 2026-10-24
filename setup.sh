#!/usr/bin/env bash
# ==============================================================================
# ArchSetup: Modern TUI Post-Installation Suite for Arch Linux + Hyprland
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Safety check: Do not execute directly as root
if [[ "$EUID" -eq 0 ]]; then
    echo -e "\e[31m[ERROR]\e[0m Please run this script as your regular user, not root."
    echo -e "        Root permissions will be requested automatically via sudo when necessary."
    exit 1
fi

# Ensure essential bootstrap tools and TUI runtime are available
BOOTSTRAP_PKGS=()
for pkg in python python-rich git base-devel; do
    if ! pacman -Qi "$pkg" &>/dev/null; then
        BOOTSTRAP_PKGS+=("$pkg")
    fi
done

if [[ ${#BOOTSTRAP_PKGS[@]} -gt 0 ]]; then
    echo -e "\e[36m[INFO]\e[0m Initializing pacman databases and installing bootstrap tools: ${BOOTSTRAP_PKGS[*]}..."
    sudo pacman -Sy --needed --noconfirm "${BOOTSTRAP_PKGS[@]}"
fi

# Launch Python orchestrator with all arguments preserved
exec python3 "$SCRIPT_DIR/core/main.py" "$@"

